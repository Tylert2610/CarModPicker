from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import Response
from uuid6 import uuid7
from webbpulse.log_context import request_id_var

#: The attribute `webbpulse.http.request_id` reads off `request.state`. The shared
#: package's error envelope calls that function to fill `request_id`, so the id this
#: middleware mints has to land there as well as in the log ContextVar, or every error
#: body would carry the placeholder "-" while the log lines carried the real id.
#: Set through the same name the package uses rather than a CarModPicker one, because
#: it is the package that reads it.
_WEBBPULSE_REQUEST_ID_STATE = "webbpulse_request_id"


async def request_context_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    req_id = request.headers.get("X-Request-ID") or str(uuid7())
    setattr(request.state, _WEBBPULSE_REQUEST_ID_STATE, req_id)
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(token)
