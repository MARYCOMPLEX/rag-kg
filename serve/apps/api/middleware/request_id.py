"""Inject `X-Request-Id` into the request scope and echo it on the response.

Pure ASGI so it composes cleanly with FastAPI / Starlette without depending on
the `BaseHTTPMiddleware` event loop overhead.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_STATE_KEY = "request_id"

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _new_id() -> str:
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """ASGI middleware: sets `request.state.request_id` and echoes the header."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        headers_raw: list[tuple[bytes, bytes]] = list(scope.get("headers") or [])
        request_id: str | None = None
        for key, value in headers_raw:
            if key == REQUEST_ID_HEADER:
                try:
                    request_id = value.decode("ascii")
                except UnicodeDecodeError:
                    request_id = None
                break
        if not request_id:
            request_id = _new_id()
        rid: str = request_id

        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state[REQUEST_ID_STATE_KEY] = rid

        async def send_with_header(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER, rid.encode("ascii")))
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, send_with_header)


def get_request_id(request: Any) -> str:
    """Helper for handlers and route functions."""
    rid = getattr(request.state, REQUEST_ID_STATE_KEY, None)
    if isinstance(rid, str) and rid:
        return rid
    return _new_id()
