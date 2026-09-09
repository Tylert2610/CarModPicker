"""Log configuration, on top of the shared package's JSON formatter.

`webbpulse.logging.configure_logging` is now what installs the root handler.
It writes one JSON object per line to stdout with a top-level `level` and an
RFC 3339 `timestamp`, which is the pair Lambda needs: with a function's log
format set to JSON, Lambda filters on an application supplied `level` and an
unparseable `timestamp` makes it stamp its own time and assign INFO, silently
defeating both `application_log_level` filtering and the `{ $.level = "ERROR" }`
metric filter behind the `api-alarms` module. The hand-rolled
`python-json-logger` setup this replaces emitted `timestamp` through
`rename_fields`, so the field names are unchanged in CloudWatch.

## What stayed here, and why

The request context filter is now the package's. `webbpulse.log_context`
0.7.0 hoisted what used to be CarModPicker's `RequestContextFilter` and
`log_context.py`, so `LogContextFilter` and `attach_log_context` replace
both. They copy `request_id` and `user_id` off the same two ContextVars
onto every record, which is what OBS-04 and `tests/test_log_propagation.py`
assert, and what keeps `filter @message like /req=bg:crawler/` working in
CloudWatch Insights. The package's JSON formatter merges the same context
itself, so the filter matters only for the TTY branch below, whose format
string references `%(request_id)s` and would raise without the attributes.

The TTY path also stayed. `configure_logging` is unconditionally JSON, and a
developer running the application locally wants the colorized single line, so
`configure_app_logging` keeps that branch and only delegates to the package when
stdout is not a TTY. That keeps local output readable while every deployed
process, where stdout is a pipe, gets the shared JSON.

The stream is the third local difference. The package logs to stdout; here the
handler is moved to stderr, which is where the `logging.basicConfig` setup this
replaces already put it. CarModPicker has two commands whose stdout is data
rather than log output, `scripts/generate_ext_api_contract.py --stdout` and the
OpenAPI snapshot regeneration, and both are compared byte for byte by a test, so
one interleaved WARNING on stdout corrupts them. Lambda captures both streams
into the same log group, so nothing is lost by the move.
"""

import logging
import sys
from copy import copy

import click
from webbpulse.log_context import attach_log_context
from webbpulse.logging import configure_logging as _configure_json_logging

# Human-readable format for TTY (local dev)
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [req=%(request_id)s user=%(user_id)s] - %(message)s"

# Level name colors (matches uvicorn default)
TRACE_LOG_LEVEL = 5
LEVEL_NAME_COLORS = {
    TRACE_LOG_LEVEL: lambda name: click.style(str(name), fg="blue"),
    logging.DEBUG: lambda name: click.style(str(name), fg="cyan"),
    logging.INFO: lambda name: click.style(str(name), fg="green"),
    logging.WARNING: lambda name: click.style(str(name), fg="yellow"),
    logging.ERROR: lambda name: click.style(str(name), fg="red"),
    logging.CRITICAL: lambda name: click.style(str(name), fg="bright_red"),
}


class ColorizedFormatter(logging.Formatter):
    """
    Formatter that colorizes the log level name (like uvicorn).
    Only enables colors when stdout is a TTY.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        use_colors: bool | None = None,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_colors = use_colors if use_colors is not None else sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy(record)
        if self.use_colors:
            color_fn = LEVEL_NAME_COLORS.get(record_copy.levelno, lambda name: str(name))
            record_copy.levelname = color_fn(record_copy.levelname)
        return super().format(record_copy)


def _redirect_handlers_to_stderr(root: logging.Logger) -> None:
    """Move the root's stdout stream handlers onto stderr, keeping the formatter.

    `webbpulse.logging.configure_logging` writes to stdout, which is right for a
    service whose stdout is only ever log output. CarModPicker has processes
    where it is not: `scripts/generate_ext_api_contract.py --stdout` writes
    Markdown to stdout and the drift guard in
    `tests/test_ext_api_contract_up_to_date.py` compares it byte for byte, so a
    single WARNING interleaved on the same stream corrupts the contract. The
    same applies to the OpenAPI snapshot regeneration command in
    `tests/test_openapi_snapshot.py`, which pipes stdout to a file.

    Logs go to stderr instead, which is where the previous `logging.basicConfig`
    setup put them, so this preserves CarModPicker's behaviour rather than
    changing it. Nothing is lost on Lambda: the execution environment captures
    both streams into the same log group, and the JSON formatter and its
    `level`/`timestamp` keys are untouched, so Lambda's JSON log filtering and
    the `{ $.level = "ERROR" }` metric filter still see what they need.
    """
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is sys.stdout:
            handler.setStream(sys.stderr)


def configure_app_logging(level: str = "INFO", service: str | None = None, environment: str | None = None) -> None:
    """Configure the root logger: shared JSON when deployed, colorized on a TTY.

    Idempotent. The package's own `configure_logging` short-circuits a second
    call, and the TTY branch replaces its handler rather than adding to it, so
    calling this from both an import and a `main()` leaves one handler either
    way rather than duplicating every line.
    """
    if sys.stdout.isatty():
        # Local development. `configure_logging` is unconditionally JSON, which
        # is unreadable at a terminal, so the colorized formatter stays for this
        # branch only. Handlers are replaced, not appended, for the same reason
        # the package replaces Lambda's: a second handler doubles every line.
        root = logging.getLogger()
        for existing in root.handlers[:]:
            root.removeHandler(existing)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColorizedFormatter(LOG_FORMAT))
        root.addHandler(handler)
        root.setLevel(level.upper())
    else:
        _configure_json_logging(level=level, service=service, environment=environment)

    root = logging.getLogger()
    _redirect_handlers_to_stderr(root)
    attach_log_context(root)


# Logger setup. `get_logger` is still exported per D-36; the `Depends(get_logger)`
# call-site pattern is what `tests/test_logger_migration_regression.py` forbids,
# not the export itself.
logger = logging.getLogger(__name__)


def get_logger() -> logging.Logger:
    return logger
