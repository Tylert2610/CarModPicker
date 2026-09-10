"""Split plan row 28: seam 2's part purge cascade, drained off the `parts` stream.

Three layers, and the middle one is the reason this file exists.

The first drives `app.consumers.part_purge` against fakes. The handler is a pure
function of a batch and a client or a bundle, and the properties that matter
(which records are tombstones, one message per part however many records, which
identifiers come back on a failure) are about grouping and reporting rather than
about AWS.

The second is the idempotency layer, and the task this row came with named it as
mandatory: every delete step has to be safe under retries and under bisect. That
is not a property a single assertion shows, so it is tested three ways. Replaying
one message reaches the same state. Replaying a batch after a mid-cascade failure
reaches the same state. And a bisected batch, where the successful half is
re-delivered alongside the failing record, reaches the same state as if it had
succeeded first time. The third is the one that is easy to get wrong, because it
is the case where a step that already ran runs again with the rows it created
gone.

The third layer runs the cascade against moto through the real repositories, so
the wire format and the delete semantics the fakes assume are checked against
what `VoteRepository`, `ReportRepository`, `BuildListPartRepository` and
`PartPriceAlertRepository` actually do. A fake that agrees with a wrong
assumption proves nothing.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from app.consumers.part_purge import (
    MESSAGE_KIND,
    MESSAGE_VERSION,
    group_records_by_part,
    handle_queue,
    handle_stream,
    is_queue_event,
    message_body,
    part_id_from_message,
    part_id_from_record,
    process_queue_records,
    process_stream_records,
    purge_related_rows,
)

QUEUE_URL = "https://sqs.us-west-2.amazonaws.com/123456789012/carmodpicker-test-part-purge"


def stream_record(
    part_id: str | None = None,
    sequence_number: str = "1",
    event_name: str = "MODIFY",
    deleted: bool = True,
    previously_deleted: bool = False,
    include_new_image: bool = True,
) -> Dict[str, Any]:
    """One `parts` stream record in the shape an event source mapping delivers.

    The low level wire format is the point: `{"BOOL": true}` rather than a plain
    `True`, and `{"S": "..."}` rather than a plain string. A helper that emitted
    plain Python values would let a handler bug through that production would hit
    on its first invoke.
    """
    part_id = part_id or str(uuid4())
    new_image = {
        "id": {"S": part_id},
        "name": {"S": "A part"},
        "deleted": {"BOOL": deleted},
        "deleted_at": {"S": "2026-09-09T00:00:00Z"} if deleted else {"NULL": True},
    }
    old_image = {
        "id": {"S": part_id},
        "name": {"S": "A part"},
        "deleted": {"BOOL": previously_deleted},
    }

    dynamodb: Dict[str, Any] = {
        "Keys": {"id": {"S": part_id}},
        "OldImage": old_image,
        "SequenceNumber": sequence_number,
        "StreamViewType": "NEW_AND_OLD_IMAGES",
    }
    if include_new_image:
        dynamodb["NewImage"] = new_image

    return {
        "eventID": sequence_number,
        "eventName": event_name,
        "eventSource": "aws:dynamodb",
        "sequenceNumber": sequence_number,
        "dynamodb": dynamodb,
    }


def queue_record(part_id: str | None = None, message_id: str = "m1") -> Dict[str, Any]:
    """One SQS record in the shape an SQS event source mapping delivers."""
    return {
        "messageId": message_id,
        "receiptHandle": f"receipt-{message_id}",
        "body": message_body(UUID(part_id or str(uuid4()))),
        "eventSource": "aws:sqs",
        "awsRegion": "us-west-2",
    }


class FakeSqs:
    """Records what was sent, and can be told to fail for one part."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, str]] = []
        self.fail_for: set[str] = set()

    def send_message(self, QueueUrl: str, MessageBody: str) -> Dict[str, str]:  # noqa: N803
        payload = json.loads(MessageBody)
        if payload["part_id"] in self.fail_for:
            raise RuntimeError("SQS is unavailable")
        self.sent.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})
        return {"MessageId": "sent"}

    @property
    def sent_part_ids(self) -> List[str]:
        return [json.loads(entry["MessageBody"])["part_id"] for entry in self.sent]


class FakeDeleteForEntities:
    """A `votes` or `reports` repository: query-then-delete, counted."""

    def __init__(self, rows: Dict[str, int]) -> None:
        # part id -> how many rows currently reference it
        self.rows = dict(rows)
        self.calls: List[UUID] = []
        self.fail_for: set[str] = set()

    def delete_for_entities(self, entity_type: str, entity_ids: List[UUID]) -> int:
        assert entity_type == "part"
        removed = 0
        for entity_id in entity_ids:
            self.calls.append(entity_id)
            if str(entity_id) in self.fail_for:
                raise RuntimeError("DynamoDB throttled")
            # The real repositories query and then delete exactly what they
            # found, so a second call finds nothing and removes nothing. That
            # is the behaviour being modelled here.
            removed += self.rows.pop(str(entity_id), 0)
        return removed


class FakeUsage:
    def __init__(self, usage_id: str) -> None:
        self.id = usage_id


class FakeBuildListParts:
    """Query by index, then batch delete the ids found."""

    def __init__(self, rows: Dict[str, List[str]]) -> None:
        self.rows = {key: list(value) for key, value in rows.items()}
        self.queries: List[UUID] = []
        self.deleted: List[List[str]] = []
        self.fail_for: set[str] = set()

    def query_all(self, index: str, key_value: Any) -> List[FakeUsage]:
        assert index == "part_id-index"
        self.queries.append(key_value)
        if str(key_value) in self.fail_for:
            raise RuntimeError("DynamoDB throttled")
        return [FakeUsage(usage_id) for usage_id in self.rows.get(str(key_value), [])]

    def batch_delete(self, keys: List[str]) -> None:
        self.deleted.append(list(keys))
        for part_id, usage_ids in self.rows.items():
            self.rows[part_id] = [usage_id for usage_id in usage_ids if usage_id not in set(keys)]


class FakeAlerts:
    def __init__(self, rows: Dict[str, int]) -> None:
        self.rows = dict(rows)
        self.calls: List[List[UUID]] = []
        self.fail_for: set[str] = set()

    def delete_for_parts(self, part_ids: List[UUID]) -> int:
        self.calls.append(list(part_ids))
        removed = 0
        for part_id in part_ids:
            if str(part_id) in self.fail_for:
                raise RuntimeError("DynamoDB throttled")
            removed += self.rows.pop(str(part_id), 0)
        return removed


class FakeRepos:
    def __init__(
        self,
        votes: FakeDeleteForEntities,
        reports: FakeDeleteForEntities,
        build_list_parts: FakeBuildListParts,
        part_price_alerts: FakeAlerts,
    ) -> None:
        self.votes = votes
        self.reports = reports
        self.build_list_parts = build_list_parts
        self.part_price_alerts = part_price_alerts

    def is_empty_for(self, part_id: str) -> bool:
        """Whether the cascade has removed everything referencing this part."""
        return (
            part_id not in self.votes.rows
            and part_id not in self.reports.rows
            and not self.build_list_parts.rows.get(part_id)
            and part_id not in self.part_price_alerts.rows
        )


def build_world(part_id: str) -> FakeRepos:
    """A part with one row in each of the four cascade tables."""
    return FakeRepos(
        votes=FakeDeleteForEntities({part_id: 3}),
        reports=FakeDeleteForEntities({part_id: 1}),
        build_list_parts=FakeBuildListParts({part_id: ["usage-a", "usage-b"]}),
        part_price_alerts=FakeAlerts({part_id: 2}),
    )


class TestRecordParsing:
    def test_a_tombstone_yields_its_part_id(self) -> None:
        part_id = str(uuid4())
        assert part_id_from_record(stream_record(part_id=part_id)) == UUID(part_id)

    def test_an_ordinary_edit_is_ignored(self) -> None:
        """The overwhelming majority of what this stream carries."""
        assert part_id_from_record(stream_record(deleted=False)) is None

    def test_an_already_tombstoned_row_is_ignored(self) -> None:
        """The cascade for it is already in flight or already done."""
        record = stream_record(deleted=True, previously_deleted=True)
        assert part_id_from_record(record) is None

    def test_a_remove_is_ignored(self) -> None:
        """The hard delete that follows a drained cascade must not re-enqueue it."""
        record = stream_record(event_name="REMOVE", include_new_image=False)
        assert part_id_from_record(record) is None

    def test_a_malformed_id_is_ignored_rather_than_raising(self) -> None:
        record = stream_record()
        record["dynamodb"]["NewImage"]["id"] = {"S": "not-a-uuid"}
        assert part_id_from_record(record) is None

    def test_a_missing_id_is_ignored(self) -> None:
        record = stream_record()
        del record["dynamodb"]["NewImage"]["id"]
        assert part_id_from_record(record) is None


class TestGrouping:
    def test_many_records_on_one_part_collapse_to_one_unit(self) -> None:
        part_id = str(uuid4())
        records = [stream_record(part_id=part_id, sequence_number=str(n), previously_deleted=False) for n in range(5)]
        grouped = group_records_by_part(records)
        assert list(grouped) == [UUID(part_id)]
        assert grouped[UUID(part_id)] == ["0", "1", "2", "3", "4"]

    def test_records_for_different_parts_stay_separate(self) -> None:
        first, second = str(uuid4()), str(uuid4())
        grouped = group_records_by_part(
            [
                stream_record(part_id=first, sequence_number="1"),
                stream_record(part_id=second, sequence_number="2"),
            ]
        )
        assert set(grouped) == {UUID(first), UUID(second)}

    def test_the_sequence_number_falls_back_to_the_nested_one(self) -> None:
        record = stream_record(sequence_number="42")
        del record["sequenceNumber"]
        grouped = group_records_by_part([record])
        assert list(grouped.values()) == [["42"]]


class TestStreamHalf:
    def test_a_tombstone_is_enqueued_once(self) -> None:
        part_id = str(uuid4())
        client = FakeSqs()
        failures = process_stream_records(client, QUEUE_URL, [stream_record(part_id=part_id)])
        assert failures == []
        assert client.sent_part_ids == [part_id]
        assert client.sent[0]["QueueUrl"] == QUEUE_URL

    def test_the_message_body_carries_only_the_part_id(self) -> None:
        """A snapshot of the related rows would let a retry act on stale state."""
        part_id = uuid4()
        payload = json.loads(message_body(part_id))
        assert payload == {"version": MESSAGE_VERSION, "kind": MESSAGE_KIND, "part_id": str(part_id)}

    def test_fifty_records_on_one_part_send_one_message(self) -> None:
        part_id = str(uuid4())
        client = FakeSqs()
        records = [stream_record(part_id=part_id, sequence_number=str(n)) for n in range(50)]
        process_stream_records(client, QUEUE_URL, records)
        assert len(client.sent) == 1

    def test_a_failed_send_reports_every_record_that_asked_for_it(self) -> None:
        part_id = str(uuid4())
        client = FakeSqs()
        client.fail_for.add(part_id)
        records = [stream_record(part_id=part_id, sequence_number=str(n)) for n in range(3)]
        failures = process_stream_records(client, QUEUE_URL, records)
        assert failures == ["0", "1", "2"]

    def test_one_failing_part_does_not_stop_the_others(self) -> None:
        bad, good = str(uuid4()), str(uuid4())
        client = FakeSqs()
        client.fail_for.add(bad)
        failures = process_stream_records(
            client,
            QUEUE_URL,
            [
                stream_record(part_id=bad, sequence_number="1"),
                stream_record(part_id=good, sequence_number="2"),
            ],
        )
        assert failures == ["1"]
        assert client.sent_part_ids == [good]

    def test_handle_stream_returns_the_mapping_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PART_PURGE_QUEUE_URL", QUEUE_URL)
        client = FakeSqs()
        result = handle_stream({"Records": [stream_record()]}, client)
        assert result == {"batchItemFailures": []}

    def test_a_missing_queue_url_raises_rather_than_acking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Acking a batch with nothing enqueued is exactly the loss this avoids."""
        monkeypatch.delenv("PART_PURGE_QUEUE_URL", raising=False)
        with pytest.raises(RuntimeError, match="PART_PURGE_QUEUE_URL"):
            handle_stream({"Records": [stream_record()]}, FakeSqs())


class TestQueueHalf:
    def test_a_message_drains_all_four_tables(self) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        failures = process_queue_records(repos, [queue_record(part_id=part_id)])
        assert failures == []
        assert repos.is_empty_for(part_id)

    def test_the_counts_are_reported(self) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        removed = purge_related_rows(repos, UUID(part_id))
        assert removed == {"votes": 3, "reports": 1, "build_list_parts": 2, "part_price_alerts": 2}

    def test_a_failing_cascade_reports_its_message(self) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        repos.reports.fail_for.add(part_id)
        failures = process_queue_records(repos, [queue_record(part_id=part_id, message_id="m9")])
        assert failures == ["m9"]

    def test_one_failing_message_does_not_stop_the_others(self) -> None:
        bad, good = str(uuid4()), str(uuid4())
        repos = FakeRepos(
            votes=FakeDeleteForEntities({bad: 1, good: 1}),
            reports=FakeDeleteForEntities({bad: 1, good: 1}),
            build_list_parts=FakeBuildListParts({bad: ["x"], good: ["y"]}),
            part_price_alerts=FakeAlerts({bad: 1, good: 1}),
        )
        repos.votes.fail_for.add(bad)
        failures = process_queue_records(
            repos,
            [queue_record(part_id=bad, message_id="m1"), queue_record(part_id=good, message_id="m2")],
        )
        assert failures == ["m1"]
        assert repos.is_empty_for(good)

    def test_an_unreadable_body_is_dropped_rather_than_retried(self) -> None:
        """Five receives on a message no retry can fix would only spend the DLQ."""
        record = queue_record()
        record["body"] = "not json at all"
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_a_body_without_a_part_id_is_dropped(self) -> None:
        record = queue_record()
        record["body"] = json.dumps({"version": 1, "kind": MESSAGE_KIND})
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_a_malformed_part_id_is_dropped(self) -> None:
        record = queue_record()
        record["body"] = json.dumps({"version": 1, "kind": MESSAGE_KIND, "part_id": "nope"})
        assert process_queue_records(build_world(str(uuid4())), [record]) == []

    def test_part_id_from_message_round_trips(self) -> None:
        part_id = uuid4()
        assert part_id_from_message(message_body(part_id)) == part_id

    def test_handle_queue_returns_the_mapping_contract(self) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        result = handle_queue({"Records": [queue_record(part_id=part_id)]}, repos)
        assert result == {"batchItemFailures": []}


class TestEventDiscrimination:
    def test_an_sqs_event_is_recognised(self) -> None:
        assert is_queue_event({"Records": [queue_record()]}) is True

    def test_a_stream_event_is_recognised(self) -> None:
        assert is_queue_event({"Records": [stream_record()]}) is False

    def test_an_empty_batch_is_treated_as_a_stream_event(self) -> None:
        """Arbitrary, and consequence free: both halves answer it with no work."""
        assert is_queue_event({"Records": []}) is False


class TestIdempotency:
    """The property the whole design rests on. Mandatory per the row's brief."""

    def test_replaying_one_message_converges(self) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        record = queue_record(part_id=part_id)

        assert process_queue_records(repos, [record]) == []
        assert repos.is_empty_for(part_id)

        # The redelivery. Every step queries, finds nothing, and writes nothing.
        assert process_queue_records(repos, [record]) == []
        assert repos.is_empty_for(part_id)

    def test_a_replay_issues_no_second_delete(self) -> None:
        """Not merely harmless: the second run writes nothing at all."""
        part_id = str(uuid4())
        repos = build_world(part_id)
        purge_related_rows(repos, UUID(part_id))
        deletes_after_first = len(repos.build_list_parts.deleted)

        removed = purge_related_rows(repos, UUID(part_id))

        assert removed == {"votes": 0, "reports": 0, "build_list_parts": 0, "part_price_alerts": 0}
        assert len(repos.build_list_parts.deleted) == deletes_after_first

    def test_a_cascade_that_failed_midway_completes_on_retry(self) -> None:
        """The half-done case, which is what a retry actually encounters."""
        part_id = str(uuid4())
        repos = build_world(part_id)
        # Votes and reports succeed, then the build list query throws.
        repos.build_list_parts.fail_for.add(part_id)

        assert process_queue_records(repos, [queue_record(part_id=part_id, message_id="m1")]) == ["m1"]
        assert part_id not in repos.votes.rows, "the steps before the failure did run"
        assert repos.build_list_parts.rows[part_id], "the failing step left its rows"

        # The retry re-runs the completed steps as no-ops and finishes the rest.
        repos.build_list_parts.fail_for.clear()
        assert process_queue_records(repos, [queue_record(part_id=part_id, message_id="m1")]) == []
        assert repos.is_empty_for(part_id)

    def test_a_bisected_batch_reruns_the_successful_half_safely(self) -> None:
        """Bisect re-delivers records that already succeeded, alongside the bad one.

        This is the case the module docstring calls out as the one that has to
        hold: the successful half runs a second time with the rows it deleted
        already gone, and must neither fail nor delete anything else.
        """
        good_a, good_b, bad = str(uuid4()), str(uuid4()), str(uuid4())
        repos = FakeRepos(
            votes=FakeDeleteForEntities({good_a: 1, good_b: 1, bad: 1}),
            reports=FakeDeleteForEntities({good_a: 1, good_b: 1, bad: 1}),
            build_list_parts=FakeBuildListParts({good_a: ["a"], good_b: ["b"], bad: ["c"]}),
            part_price_alerts=FakeAlerts({good_a: 1, good_b: 1, bad: 1}),
        )
        repos.votes.fail_for.add(bad)

        batch = [
            queue_record(part_id=good_a, message_id="m1"),
            queue_record(part_id=good_b, message_id="m2"),
            queue_record(part_id=bad, message_id="m3"),
        ]
        assert process_queue_records(repos, batch) == ["m3"]
        assert repos.is_empty_for(good_a) and repos.is_empty_for(good_b)

        # The mapping bisects and re-delivers the whole batch. The two that
        # succeeded run again against rows that are already gone.
        repos.votes.fail_for.clear()
        assert process_queue_records(repos, batch) == []
        assert repos.is_empty_for(good_a)
        assert repos.is_empty_for(good_b)
        assert repos.is_empty_for(bad)

    def test_enqueueing_twice_is_safe_because_draining_twice_is(self) -> None:
        """Which is what lets the producer send without deduplication."""
        part_id = str(uuid4())
        client = FakeSqs()
        record = stream_record(part_id=part_id)
        process_stream_records(client, QUEUE_URL, [record])
        process_stream_records(client, QUEUE_URL, [record])
        assert client.sent_part_ids == [part_id, part_id]

        repos = build_world(part_id)
        records = [queue_record(part_id=part_id, message_id="m1"), queue_record(part_id=part_id, message_id="m2")]
        assert process_queue_records(repos, records) == []
        assert repos.is_empty_for(part_id)


class TestAgainstRealRepositories:
    """The same cascade against moto, so the fakes are checked against reality."""

    def test_the_cascade_removes_every_referencing_row(self, dynamo_tables: Any) -> None:
        from app.db.dynamo.build_lists import (
            BuildList,
            BuildListPart,
            BuildListPartRepository,
            BuildListRepository,
        )
        from app.db.dynamo.moderation import (
            Report,
            ReportRepository,
            Vote,
            VoteRepository,
        )
        from app.db.dynamo.part_price_alerts import PartPriceAlert, PartPriceAlertRepository

        part_id = uuid4()
        user_id = uuid4()

        votes = VoteRepository()
        reports = ReportRepository()
        build_lists = BuildListRepository()
        build_list_parts = BuildListPartRepository()
        alerts = PartPriceAlertRepository()

        votes.put(Vote(entity_type="part", entity_id=part_id, user_id=user_id, vote_type="upvote"))
        reports.put(Report(entity_type="part", entity_id=part_id, user_id=user_id, reason="spam", description="x"))
        build_list = build_lists.put(BuildList(name="A list", user_id=user_id))
        build_list_parts.put(BuildListPart(build_list_id=build_list.id, part_id=part_id, added_by=user_id))
        alerts.put(PartPriceAlert(part_id=part_id, user_id=user_id, threshold_cents=100))

        class RealRepos:
            def __init__(self) -> None:
                self.votes = votes
                self.reports = reports
                self.build_list_parts = build_list_parts
                self.part_price_alerts = alerts

        repos = RealRepos()

        removed = purge_related_rows(repos, part_id)
        assert removed["votes"] == 1
        assert removed["reports"] == 1
        assert removed["build_list_parts"] == 1
        assert removed["part_price_alerts"] == 1

        assert votes.for_entities("part", [part_id]).get(part_id, []) == []
        assert [r for r in reports.for_entity("part", part_id)] == []
        assert build_list_parts.query_all("part_id-index", part_id) == []
        assert alerts.list_by_part(part_id) == []

    def test_the_replay_against_real_repositories_writes_nothing(self, dynamo_tables: Any) -> None:
        """The idempotency argument, checked against real DynamoDB semantics."""
        from app.db.dynamo.build_lists import BuildListPartRepository
        from app.db.dynamo.moderation import (
            Report,
            ReportRepository,
            Vote,
            VoteRepository,
        )
        from app.db.dynamo.part_price_alerts import PartPriceAlertRepository

        part_id = uuid4()
        user_id = uuid4()
        votes = VoteRepository()
        reports = ReportRepository()
        votes.put(Vote(entity_type="part", entity_id=part_id, user_id=user_id, vote_type="upvote"))
        reports.put(Report(entity_type="part", entity_id=part_id, user_id=user_id, reason="spam", description="x"))

        class RealRepos:
            def __init__(self) -> None:
                self.votes = votes
                self.reports = reports
                self.build_list_parts = BuildListPartRepository()
                self.part_price_alerts = PartPriceAlertRepository()

        repos = RealRepos()
        assert purge_related_rows(repos, part_id)["votes"] == 1

        # A DeleteItem on a key that is not there succeeds, so the replay is a
        # no-op rather than an error.
        second = purge_related_rows(repos, part_id)
        assert second == {"votes": 0, "reports": 0, "build_list_parts": 0, "part_price_alerts": 0}


class TestEntrypoint:
    @staticmethod
    def client(monkeypatch: pytest.MonkeyPatch, repos: Any, sqs: Any) -> Any:
        from fastapi.testclient import TestClient

        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "repositories", lambda: repos)
        monkeypatch.setattr(entrypoint, "sqs_client", lambda: sqs)
        return TestClient(entrypoint.app, raise_server_exceptions=False)

    def test_health_is_served(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = self.client(monkeypatch, build_world(str(uuid4())), FakeSqs())
        assert client.get("/health").status_code == 200

    def test_a_stream_event_is_routed_to_the_producer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PART_PURGE_QUEUE_URL", QUEUE_URL)
        part_id = str(uuid4())
        sqs = FakeSqs()
        client = self.client(monkeypatch, build_world(part_id), sqs)

        response = client.post("/events", json={"Records": [stream_record(part_id=part_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert sqs.sent_part_ids == [part_id]

    def test_a_queue_event_is_routed_to_the_drainer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        sqs = FakeSqs()
        client = self.client(monkeypatch, repos, sqs)

        response = client.post("/events", json={"Records": [queue_record(part_id=part_id)]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": []}
        assert repos.is_empty_for(part_id)
        assert sqs.sent == [], "the queue half sends nothing"

    def test_a_partial_failure_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        part_id = str(uuid4())
        repos = build_world(part_id)
        repos.votes.fail_for.add(part_id)
        client = self.client(monkeypatch, repos, FakeSqs())

        response = client.post("/events", json={"Records": [queue_record(part_id=part_id, message_id="m7")]})

        assert response.status_code == 200
        assert response.json() == {"batchItemFailures": [{"itemIdentifier": "m7"}]}

    def test_an_unexpected_error_is_a_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`AWS_LWA_ERROR_STATUS_CODES=500-599` turns this into a function error."""
        from fastapi.testclient import TestClient

        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        def explode() -> Any:
            raise RuntimeError("the bundle could not be built")

        monkeypatch.setattr(entrypoint, "repositories", explode)
        client = TestClient(entrypoint.app, raise_server_exceptions=False)
        response = client.post("/events", json={"Records": [queue_record()]})
        assert response.status_code >= 500

    def test_a_malformed_body_is_a_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = self.client(monkeypatch, build_world(str(uuid4())), FakeSqs())
        response = client.post("/events", content=b"not json at all", headers={"content-type": "application/json"})
        assert response.status_code >= 500

    def test_the_service_name_distinguishes_it(self) -> None:
        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        assert entrypoint.SERVICE_NAME == f"{entrypoint.DOMAIN.service_name}-part-purge-consumer"
        assert entrypoint.SERVICE_NAME != entrypoint.DOMAIN.service_name

    def test_the_events_path_matches_the_adapter_contract(self) -> None:
        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        assert entrypoint.EVENTS_PATH == "/events"
        assert entrypoint.EVENTS_PATH in {route.path for route in entrypoint.app.routes}

    def test_neither_cors_nor_the_rate_limiter_is_mounted(self) -> None:
        """The limiter would write to a table this function has no grant for."""
        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        mounted = {middleware.cls.__name__ for middleware in entrypoint.app.user_middleware}
        assert "CORSMiddleware" not in mounted
        assert not any("RateLimit" in name for name in mounted)

    def test_the_bundle_is_memoised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.entrypoints import catalog_part_purge_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "_repos", None)
        built: List[int] = []

        def fake_build_bundle(names: Any, *, name: str = "all") -> Any:
            built.append(1)
            return object()

        monkeypatch.setattr("app.api.dependencies.repositories.build_bundle", fake_build_bundle)
        assert entrypoint.repositories() is entrypoint.repositories()
        assert len(built) == 1
        monkeypatch.setattr(entrypoint, "_repos", None)

    def test_the_bundle_carries_the_four_cascade_tables_and_nothing_else(self) -> None:
        """The narrowing this row buys, asserted rather than assumed.

        `catalog`, `vehicles`, `build-lists` and `admin` gave up
        `build_list_parts`, `reports` and `part_price_alerts` in this row. That
        is only a narrowing if the access landed somewhere smaller, so this
        pins the somewhere: four repositories on one function, not a domain
        bundle that happens to contain them.
        """
        from app.entrypoints.catalog_part_purge_consumer import REPOSITORIES

        assert set(REPOSITORIES) == {
            "build_list_parts",
            "votes",
            "reports",
            "part_price_alerts",
        }

    def test_the_domains_that_gave_up_the_cascade_tables_no_longer_carry_them(self) -> None:
        """The other half of the same claim, from the domains' side.

        Written as an explicit assertion because the bundle test that caught
        this proves only that nothing reaches them, which would also be true if
        the tables had simply stopped being used anywhere.
        """
        from app.composition.domains import DOMAINS

        assert "build_list_parts" not in DOMAINS["catalog"].repositories
        assert "reports" not in DOMAINS["catalog"].repositories
        assert "part_price_alerts" not in DOMAINS["catalog"].repositories
        assert "build_list_parts" not in DOMAINS["admin"].repositories
        assert "reports" not in DOMAINS["build-lists"].repositories
        assert "part_price_alerts" not in DOMAINS["build-lists"].repositories
        # `admin` owns `part_price_alerts` and reads it on its own routes, so it
        # keeps it. The row removes borrowed access, not owned access.
        assert "part_price_alerts" in DOMAINS["admin"].repositories
