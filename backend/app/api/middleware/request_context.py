"""Middleware that stamps a request id onto every request and response."""

from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import Response
from uuid6 import uuid7
from webbpulse.log_context import request_id_var

_WEBBPULSE_REQUEST_ID_STATE = "webbpulse_request_id"


async def request_context_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Attach a request id to the request, response header and log context."""
    req_id = request.headers.get("X-Request-ID") or str(uuid7())
    setattr(request.state, _WEBBPULSE_REQUEST_ID_STATE, req_id)
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(token)
