"""Log configuration on top of the shared package's JSON formatter.

Deployed processes get the shared JSON lines; a TTY gets a colorized line instead.
Handlers move to stderr either way, since some commands write data on stdout.
"""

import logging
import sys
from copy import copy

import click
from webbpulse.log_context import attach_log_context
from webbpulse.logging import configure_logging as _configure_json_logging

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [req=%(request_id)s user=%(user_id)s] - %(message)s"

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
    """Formatter that colorizes the log level name, the way uvicorn does.

    Colors are enabled only when stdout is a TTY.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        use_colors: bool | None = None,
    ) -> None:
        """Take the format strings, defaulting color use to whether stdout is a TTY."""
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_colors = use_colors if use_colors is not None else sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format a copy of the record, with the level name colorized when enabled."""
        record_copy = copy(record)
        if self.use_colors:
            color_fn = LEVEL_NAME_COLORS.get(record_copy.levelno, lambda name: str(name))
            record_copy.levelname = color_fn(record_copy.levelname)
        return super().format(record_copy)


def _redirect_handlers_to_stderr(root: logging.Logger) -> None:
    """Move the root's stdout stream handlers onto stderr, keeping the formatter.

    Two commands write data to stdout and are compared byte for byte, so one
    interleaved log line would corrupt them. Lambda captures both streams alike.
    """
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is sys.stdout:
            handler.setStream(sys.stderr)


def configure_app_logging(level: str = "INFO", service: str | None = None, environment: str | None = None) -> None:
    """Configure the root logger: shared JSON when deployed, colorized on a TTY.

    Idempotent, so calling it from both an import and a `main()` leaves one
    handler rather than duplicating every line.
    """
    if sys.stdout.isatty():
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


logger = logging.getLogger(__name__)


def get_logger() -> logging.Logger:
    """This module's logger."""
    return logger
