"""OBS-04 regression guard — every log record during a request scope MUST have
non-default request_id + user_id. Fails CI if a future dev adds a handler that
drops LogContextFilter coverage or uses print() instead of logger.

Decision refs: 02-CONTEXT.md D-44 (audit, not redesign), D-45 (regression guard),
D-46 (background task context), D-47 (CLI context).

`task_context` is `webbpulse.log_context`'s name for what used to be
CarModPicker's `bg_log_context`; the package emits the identical
`bg:{task}:{job or "-"}` request id and `user_id="bg"`, so the CloudWatch
Insights queries and the assertions below are unchanged.

Landmine: pytest caplog does NOT inherit root-logger filters — the
`caplog_with_context` fixture (conftest.py) attaches `LogContextFilter`
to caplog.handler so records carry request_id + user_id attributes.
Without this fixture, every assertion below AttributeErrors.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from webbpulse.log_context import (
    request_id_var,
    task_context,
    user_id_var,
)

from app.db.dynamo.users import User
from tests.conftest import auth_headers, login_user

# Loggers whose records OBS-04 actually governs: this application's own, plus
# the shared package it runs on.  Everything else captured during a TestClient
# request is third party plumbing that emits outside the middleware scope --
# TestClient's HTTP transport and the event loop fire before the middleware sets
# the ContextVars, botocore logs from inside the mocked AWS calls, and
# python_multipart runs during form parsing before the middleware adds user
# context.  In production (uvicorn + real HTTP) those same loggers also run
# outside request scope and are not subject to the invariant either.
#
# Deliberately an allowlist of what IS in scope rather than a denylist of what
# is not.  A denylist has to name every third party logger that might ever emit
# during a request, so it silently stops testing anything the moment a
# dependency renames its logger or a new one appears: `httpx` becoming `httpx2`
# in a newer starlette turned this assertion into a failure about somebody
# else's log record.  An allowlist cannot rot that way, because the set of
# loggers OBS-04 is about is the set this repository controls.
_IN_SCOPE_LOGGER_ROOTS = (
    "app",
    "webbpulse",
)


def _in_request_scope(rec: logging.LogRecord) -> bool:
    """True if the record comes from code that should be inside a request scope."""
    return any(rec.name == n or rec.name.startswith(f"{n}.") for n in _IN_SCOPE_LOGGER_ROOTS)


def test_log_propagation_request_scope(
    client: TestClient,
    test_user: User,
    caplog_with_context,
) -> None:
    """Every in-scope log record during an authenticated request has non-default
    request_id + user_id.  We inject a dependency override on get_current_user
    that calls the original dependency (so user_id_var.set runs) and THEN emits
    an app-logger record from inside the request scope.  This proves:

      * request_context_middleware populated request_id_var (per-request UUID)
      * get_current_user populated user_id_var (authenticated user UUID)
      * LogContextFilter wired both ContextVars into the LogRecord

    "In-scope" = records emitted by this application or the shared package, not
    by third party plumbing; see `_IN_SCOPE_LOGGER_ROOTS`.
    """
    from fastapi import Depends

    from app.api.dependencies.auth import get_current_user, oauth2_scheme
    from app.api.dependencies.repositories import Repositories, get_repositories
    from app.main import app as fastapi_app

    emitted_request_ids: list[str] = []
    emitted_user_ids: list[str] = []

    # Override with a FastAPI-compatible signature so Depends() introspection works.
    async def logging_current_user(
        request: Request,
        token: str = Depends(oauth2_scheme),
        repos: Repositories = Depends(get_repositories),
    ) -> User:
        # `request` is threaded through since row 11: `get_current_user` reads
        # the authorizer's claims off it when the bearer token is not a legacy
        # session. This override is standing in for the real dependency, so it
        # has to take the same arguments the real one does.
        result = await get_current_user(request=request, token=token, repos=repos)
        test_logger = logging.getLogger("app.tests.log_propagation")
        test_logger.info("post-auth request scope log emit")
        emitted_request_ids.append(request_id_var.get())
        emitted_user_ids.append(user_id_var.get())
        return result

    # Build the credential OUTSIDE caplog capture so the repository read
    # `login_user` performs does not pollute the authenticated-request
    # assertion.
    credential = login_user(client, test_user.username)

    caplog_with_context.set_level(logging.DEBUG)
    caplog_with_context.clear()

    fastapi_app.dependency_overrides[get_current_user] = logging_current_user
    try:
        response = client.get("/api/users/me", headers=auth_headers(credential))
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200, response.text

    # ContextVars observed inside the override were populated.
    assert len(emitted_request_ids) == 1, "override did not run exactly once"
    assert emitted_request_ids[0] != "-", "request_id_var not set inside request scope"
    assert emitted_user_ids[0] != "-", "user_id_var not set after get_current_user ran"

    # In-scope log records captured by caplog carry both context fields.
    in_scope = [r for r in caplog_with_context.records if _in_request_scope(r)]
    assert len(in_scope) > 0, "no in-scope log records captured during request"
    for rec in in_scope:
        assert getattr(rec, "request_id", "-") != "-", f"missing request_id on '{rec.getMessage()}' (logger={rec.name})"
        assert getattr(rec, "user_id", "-") != "-", f"missing user_id on '{rec.getMessage()}' (logger={rec.name})"


def test_task_context(caplog_with_context) -> None:
    """task_context sets request_id=bg:{task}:{job} + user_id=bg."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with task_context("crawler", "job-1"):
        logger.info("running bg task")
    matches = [r for r in caplog_with_context.records if "running bg task" in r.getMessage()]
    assert len(matches) == 1
    rec = matches[0]
    assert rec.request_id == "bg:crawler:job-1"
    assert rec.user_id == "bg"


def test_task_context_job_id_none(caplog_with_context) -> None:
    """task_context with no job_id renders 'bg:{task}:-'."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with task_context("sweep"):
        logger.info("sweep running")
    rec = next(r for r in caplog_with_context.records if "sweep running" in r.getMessage())
    assert rec.request_id == "bg:sweep:-"


def test_task_context_resets(caplog_with_context) -> None:
    """Token-based reset restores whatever the ContextVars held before entry.

    The baseline is pinned explicitly rather than assumed to be the `"-"`
    default. Under xdist another test on the same worker can leave a request
    id behind, and `task_context` restores the previous value by token, so
    asserting the module default made this test depend on scheduling order.
    """
    rid_token = request_id_var.set("before-rid")
    uid_token = user_id_var.set("before-uid")
    try:
        with task_context("scope", "1"):
            assert request_id_var.get() == "bg:scope:1"
            assert user_id_var.get() == "bg"
        assert request_id_var.get() == "before-rid"
        assert user_id_var.get() == "before-uid"
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)


def test_cli_log_context(caplog_with_context) -> None:
    """CLI scope produces request_id=cli:<pid>, user_id=cli."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.cli")
    rid_token = request_id_var.set("cli:12345")
    uid_token = user_id_var.set("cli")
    try:
        logger.info("cli startup")
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
    rec = next(r for r in caplog_with_context.records if "cli startup" in r.getMessage())
    assert rec.request_id == "cli:12345"
    assert rec.user_id == "cli"
