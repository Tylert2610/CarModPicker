"""Split plan row 24: the `votes` stream consumer that recomputes `net_votes`.

Two layers of test here, deliberately.

The first drives `app.consumers.votes` against fake repositories. The unit under
test is a pure function of a batch and a repository pair, and the properties that
matter (one recompute per part, tombstones skipped, which sequence numbers come
back on a failure) are all about how the handler groups and reports, not about
DynamoDB. Fakes let each of those be asserted exactly, including the counts of
calls made, which is the only way to show that fifty records on one part are one
query rather than fifty.

The second runs the same handler against moto through the real repositories, so
the wire format the fakes assume is checked against the one the real
`PartRepository` and `VoteRepository` produce. A fake that agrees with a wrong
assumption proves nothing; this is what stops that.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid4

import pytest

from app.consumers.votes import (
    group_records_by_part,
    handle,
    part_id_from_record,
    process_records,
    recompute_net_votes,
)
from app.db.dynamo.catalog import Category, CategoryRepository, Part, PartRepository
from app.db.dynamo.moderation import Vote, VoteRepository
from app.db.dynamo.repository import ItemNotFound


def stream_record(
    entity_type: str = "part",
    entity_id: str | None = None,
    sequence_number: str = "1",
    event_name: str = "INSERT",
    image_key: str = "NewImage",
) -> Dict[str, Any]:
    """One DynamoDB stream record in the shape an event source mapping delivers.

    The low level wire format is the point: `{"S": "..."}` rather than a plain
    string. A helper that emitted plain strings would let a handler bug through
    that production would hit on its first invoke.
    """
    image = {
        "id": {"S": str(uuid4())},
        "entity_type": {"S": entity_type},
        "entity_id": {"S": entity_id or str(uuid4())},
        "vote_type": {"S": "upvote"},
    }
    return {
        "eventID": sequence_number,
        "eventName": event_name,
        "eventSource": "aws:dynamodb",
        "sequenceNumber": sequence_number,
        "dynamodb": {
            "Keys": {"id": image["id"]},
            image_key: image,
            "SequenceNumber": sequence_number,
            "StreamViewType": "NEW_AND_OLD_IMAGES",
        },
    }


class FakeParts:
    def __init__(self, parts: Dict[str, Any]) -> None:
        self.parts = parts
        self.updates: List[Tuple[str, int]] = []
        self.gets: List[str] = []
        self.raise_on_update: Exception | None = None

    def get(self, part_id: str) -> Any:
        self.gets.append(part_id)
        return self.parts.get(part_id)

    def update(self, part_id: str, **changes: Any) -> Any:
        if self.raise_on_update is not None:
            raise self.raise_on_update
        self.updates.append((part_id, changes["net_votes"]))
        part = self.parts[part_id]
        part.net_votes = changes["net_votes"]
        return part


class FakeVotes:
    def __init__(self, counts: Dict[str, Tuple[int, int]]) -> None:
        self.counts_by_entity = counts
        self.calls: List[Tuple[str, UUID]] = []

    def counts(self, entity_type: str, entity_id: UUID) -> Tuple[int, int]:
        self.calls.append((entity_type, entity_id))
        return self.counts_by_entity.get(str(entity_id), (0, 0))


class FakeRepos:
    def __init__(self, parts: FakeParts, votes: FakeVotes) -> None:
        self.parts = parts
        self.votes = votes


class FakePart:
    """Only the two attributes the consumer reads."""

    def __init__(self, net_votes: int = 0, deleted: bool = False) -> None:
        self.net_votes = net_votes
        self.deleted = deleted


class TestRecordParsing:
    def test_part_vote_yields_its_entity_id(self) -> None:
        part_id = uuid4()
        assert part_id_from_record(stream_record(entity_id=str(part_id))) == part_id

    @pytest.mark.parametrize("entity_type", ["build_list", "car_generation"])
    def test_other_entity_types_are_dropped(self, entity_type: str) -> None:
        """A build list vote must cost no DynamoDB call at all."""
        assert part_id_from_record(stream_record(entity_type=entity_type)) is None

    def test_remove_reads_the_old_image(self) -> None:
        """A REMOVE carries only `OldImage`, and the part still needs recounting."""
        part_id = uuid4()
        record = stream_record(entity_id=str(part_id), event_name="REMOVE", image_key="OldImage")
        assert part_id_from_record(record) == part_id

    def test_record_with_no_image_is_dropped(self) -> None:
        assert part_id_from_record({"sequenceNumber": "1", "dynamodb": {}}) is None

    def test_record_with_no_dynamodb_key_is_dropped(self) -> None:
        assert part_id_from_record({"sequenceNumber": "1"}) is None

    def test_malformed_entity_id_is_dropped_not_failed(self) -> None:
        """Not retryable, so it must not reach the dead letter queue."""
        record = stream_record(entity_id="not-a-uuid")
        assert part_id_from_record(record) is None

    def test_grouping_collapses_records_per_part_and_keeps_every_sequence(self) -> None:
        part_a, part_b = str(uuid4()), str(uuid4())
        records = [
            stream_record(entity_id=part_a, sequence_number="1"),
            stream_record(entity_id=part_b, sequence_number="2"),
            stream_record(entity_id=part_a, sequence_number="3"),
            stream_record(entity_type="build_list", sequence_number="4"),
        ]
        grouped = group_records_by_part(records)

        assert set(grouped) == {UUID(part_a), UUID(part_b)}
        assert grouped[UUID(part_a)] == ["1", "3"]
        assert grouped[UUID(part_b)] == ["2"]


class TestRecompute:
    def test_writes_the_difference_of_the_counts(self) -> None:
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (7, 2)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) == 5
        assert parts.updates == [(str(part_id), 5)]

    def test_missing_part_writes_nothing(self) -> None:
        """A vote can outlive its part; that is not an error."""
        part_id = uuid4()
        parts = FakeParts({})
        votes = FakeVotes({})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None
        assert parts.updates == []
        assert votes.calls == []

    def test_tombstoned_part_is_skipped(self) -> None:
        """Row 23: a part being purged must not have an attribute written back."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0, deleted=True)})
        votes = FakeVotes({str(part_id): (4, 1)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None
        assert parts.updates == []
        # The recount is not even attempted, so a tombstone costs one read.
        assert votes.calls == []

    def test_unchanged_aggregate_skips_the_write(self) -> None:
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=3)})
        votes = FakeVotes({str(part_id): (3, 0)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) == 3
        assert parts.updates == []

    def test_part_deleted_between_the_read_and_the_write(self) -> None:
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        parts.raise_on_update = ItemNotFound("carmodpicker-parts", {"id": str(part_id)})
        votes = FakeVotes({str(part_id): (2, 0)})

        assert recompute_net_votes(FakeRepos(parts, votes), part_id) is None


class TestIdempotency:
    def test_replaying_the_same_record_converges(self) -> None:
        """At-least-once delivery: the same batch twice must not double the count."""
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (5, 1)})
        repos = FakeRepos(parts, votes)
        event = {"Records": [stream_record(entity_id=str(part_id))]}

        assert handle(event, repos) == {"batchItemFailures": []}
        assert handle(event, repos) == {"batchItemFailures": []}
        assert handle(event, repos) == {"batchItemFailures": []}

        assert parts.parts[str(part_id)].net_votes == 4
        # The first pass wrote; the two replays saw the same number and skipped.
        assert parts.updates == [(str(part_id), 4)]

    def test_many_records_on_one_part_are_one_recompute(self) -> None:
        part_id = uuid4()
        parts = FakeParts({str(part_id): FakePart(net_votes=0)})
        votes = FakeVotes({str(part_id): (50, 0)})
        records = [stream_record(entity_id=str(part_id), sequence_number=str(i)) for i in range(50)]

        handle({"Records": records}, FakeRepos(parts, votes))

        assert len(votes.calls) == 1
        assert parts.updates == [(str(part_id), 50)]


class TestBatchHandling:
    def test_mixed_batch_recomputes_only_the_parts(self) -> None:
        part_a, part_b = str(uuid4()), str(uuid4())
        parts = FakeParts({part_a: FakePart(), part_b: FakePart()})
        votes = FakeVotes({part_a: (3, 1), part_b: (0, 2)})
        records = [
            stream_record(entity_id=part_a, sequence_number="1"),
            stream_record(entity_type="build_list", sequence_number="2"),
            stream_record(entity_id=part_b, sequence_number="3", event_name="REMOVE", image_key="OldImage"),
            stream_record(entity_type="car_generation", sequence_number="4"),
            stream_record(entity_id=part_a, sequence_number="5", event_name="MODIFY"),
        ]

        result = handle({"Records": records}, FakeRepos(parts, votes))

        assert result == {"batchItemFailures": []}
        assert sorted(parts.updates) == sorted([(part_a, 2), (part_b, -2)])

    def test_empty_event_returns_an_empty_failure_list(self) -> None:
        """Explicitly `{"batchItemFailures": []}`, not an empty response."""
        assert handle({}, FakeRepos(FakeParts({}), FakeVotes({}))) == {"batchItemFailures": []}

    def test_one_failing_part_reports_only_its_own_records(self) -> None:
        part_ok, part_bad = str(uuid4()), str(uuid4())

        class ExplodingVotes(FakeVotes):
            def counts(self, entity_type: str, entity_id: UUID) -> Tuple[int, int]:
                if str(entity_id) == part_bad:
                    raise RuntimeError("ProvisionedThroughputExceededException")
                return super().counts(entity_type, entity_id)

        parts = FakeParts({part_ok: FakePart(), part_bad: FakePart()})
        votes = ExplodingVotes({part_ok: (2, 0)})
        records = [
            stream_record(entity_id=part_ok, sequence_number="1"),
            stream_record(entity_id=part_bad, sequence_number="2"),
            stream_record(entity_id=part_bad, sequence_number="3"),
        ]

        result = handle({"Records": records}, FakeRepos(parts, votes))

        # Every record that asked for the failed part, not just the last one.
        assert result == {"batchItemFailures": [{"itemIdentifier": "2"}, {"itemIdentifier": "3"}]}
        # The healthy part still got its aggregate.
        assert parts.updates == [(part_ok, 2)]

    def test_process_records_returns_sequence_numbers(self) -> None:
        part_id = str(uuid4())
        parts = FakeParts({part_id: FakePart()})
        parts.raise_on_update = RuntimeError("throttled")
        votes = FakeVotes({part_id: (1, 0)})

        failures = process_records(
            FakeRepos(parts, votes),
            [stream_record(entity_id=part_id, sequence_number="99")],
        )

        assert failures == ["99"]


class TestAgainstRealRepositories:
    """The same handler, moto, and the repositories the Lambda actually builds."""

    def test_recompute_writes_the_real_part(self, dynamo_tables: Any) -> None:
        category = next(iter(CategoryRepository().list_all()), None)
        if category is None:
            category = CategoryRepository().create(
                Category(
                    name="consumer_test_category",
                    display_name="Consumer Test Category",
                    description="For the votes stream consumer test",
                    is_active=True,
                    sort_order=1,
                )
            )
        user_id = uuid4()
        part = PartRepository().create(
            Part(name=f"consumer-part-{uuid4()}", description="x", user_id=user_id, category_id=category.id)
        )

        votes = VoteRepository()
        for _ in range(3):
            votes.create(Vote(user_id=uuid4(), entity_type="part", entity_id=part.id, vote_type="upvote"))
        votes.create(Vote(user_id=uuid4(), entity_type="part", entity_id=part.id, vote_type="downvote"))

        class RealRepos:
            parts = PartRepository()
            votes = VoteRepository()

        result = handle({"Records": [stream_record(entity_id=str(part.id))]}, RealRepos())

        assert result == {"batchItemFailures": []}
        assert PartRepository().get(part.id).net_votes == 2

        # Replaying converges rather than doubling.
        handle({"Records": [stream_record(entity_id=str(part.id))]}, RealRepos())
        assert PartRepository().get(part.id).net_votes == 2


class TestEntrypoint:
    """`app.entrypoints.catalog_votes_consumer`, the tenth deployed function.

    The module is not an application, so there is no `TestClient` to point at
    it. What is worth asserting is the contract Terraform and the deploy rely
    on: the attribute the `image_config.command` names exists, it delegates to
    the handler under test, and the service name it logs under is distinct from
    the HTTP catalog function's so that "which one erred" stays answerable.
    """

    def test_handler_delegates_to_the_consumer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.entrypoints import catalog_votes_consumer as entrypoint

        part_id = str(uuid4())
        parts = FakeParts({part_id: FakePart()})
        votes = FakeVotes({part_id: (2, 0)})
        monkeypatch.setattr(entrypoint, "repositories", lambda: FakeRepos(parts, votes))

        result = entrypoint.handler({"Records": [stream_record(entity_id=part_id)]})

        assert result == {"batchItemFailures": []}
        assert parts.updates == [(part_id, 2)]

    def test_service_name_is_distinct_from_the_http_catalog_function(self) -> None:
        from app.entrypoints import catalog_votes_consumer as entrypoint

        assert entrypoint.SERVICE_NAME == f"{entrypoint.DOMAIN.service_name}-votes-consumer"
        assert entrypoint.SERVICE_NAME != entrypoint.DOMAIN.service_name

    def test_the_bundle_is_memoised_across_invokes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One bundle per execution environment, not one per invoke."""
        from app.entrypoints import catalog_votes_consumer as entrypoint

        monkeypatch.setattr(entrypoint, "_repos", None)
        built: List[int] = []

        def fake_bundle_for(domains: Any) -> Any:
            built.append(1)
            return FakeRepos(FakeParts({}), FakeVotes({}))

        monkeypatch.setattr("app.composition.wiring.bundle_for", fake_bundle_for)

        first = entrypoint.repositories()
        second = entrypoint.repositories()

        assert first is second
        assert len(built) == 1

    def test_the_module_builds_no_fastapi_application(self) -> None:
        """A stream consumer with a router would mean the split leaked."""
        from app.entrypoints import catalog_votes_consumer as entrypoint

        assert not hasattr(entrypoint, "app")
        assert not hasattr(entrypoint, "build_app")
