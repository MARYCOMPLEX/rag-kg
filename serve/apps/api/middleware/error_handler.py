"""Map every uncaught error into the unified `ErrorEnvelope` JSON shape."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.api.middleware.request_id import get_request_id
from packages.core.api_errors import ErrorCode, ErrorEnvelope
from packages.core.errors import (
    ConfigError,
    CrossLibraryReferenceError,
    LibraryAlreadyExistsError,
    LibraryNotFoundError,
    RKBError,
)
from packages.orchestration.errors import (
    QueueFullError,
    TaskHistoryExpiredError,
    TaskNotFoundError,
)

_log = logging.getLogger(__name__)

_HTTP_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.AUTH_ERROR,
    403: ErrorCode.AUTH_ERROR,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    503: ErrorCode.UPSTREAM_ERROR,
}


def _envelope(
    code: ErrorCode, message: str, request_id: str, details: object | None = None
) -> dict[str, object]:
    return ErrorEnvelope(
        code=code, message=message, request_id=request_id, details=details
    ).model_dump(mode="json")


async def _on_http(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    rid = get_request_id(request)
    code = _HTTP_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = str(exc.detail) if exc.detail else exc.__class__.__name__
    body = _envelope(code, message, rid)
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers or None)


async def _on_validation(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    rid = get_request_id(request)
    body = _envelope(
        ErrorCode.VALIDATION_ERROR,
        "Request body failed validation",
        rid,
        details=exc.errors(),
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)


async def _on_lib_404(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LibraryNotFoundError)
    rid = get_request_id(request)
    body = _envelope(
        ErrorCode.LIBRARY_NOT_FOUND,
        str(exc),
        rid,
        details={"library_id": exc.library_id},
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body)


async def _on_lib_conflict(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LibraryAlreadyExistsError)
    rid = get_request_id(request)
    body = _envelope(
        ErrorCode.LIBRARY_ALREADY_EXISTS,
        str(exc),
        rid,
        details={"library_id": exc.library_id},
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body)


async def _on_xref(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, CrossLibraryReferenceError)
    rid = get_request_id(request)
    body = _envelope(ErrorCode.VALIDATION_ERROR, str(exc), rid)
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=body)


async def _on_config(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    body = _envelope(ErrorCode.INTERNAL_ERROR, str(exc), rid)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)


async def _on_task_not_found(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskNotFoundError)
    rid = get_request_id(request)
    body = _envelope(
        ErrorCode.NOT_FOUND,
        str(exc),
        rid,
        details={"library_id": exc.library_id, "task_id": exc.task_id},
    )
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body)


async def _on_task_history_expired(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TaskHistoryExpiredError)
    rid = get_request_id(request)
    body = _envelope(
        ErrorCode.CONFLICT,
        str(exc),
        rid,
        details={"library_id": exc.library_id, "task_id": exc.task_id},
    )
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body)


async def _on_queue_full(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    body = _envelope(ErrorCode.UPSTREAM_ERROR, str(exc), rid)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)


async def _on_rkb(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    body = _envelope(ErrorCode.INTERNAL_ERROR, str(exc) or exc.__class__.__name__, rid)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)


async def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    _log.exception("unhandled exception (request_id=%s)", rid)
    body = _envelope(
        ErrorCode.INTERNAL_ERROR,
        "Internal server error",
        rid,
        details={"type": exc.__class__.__name__},
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the unified envelope handlers onto the given FastAPI app."""
    app.add_exception_handler(HTTPException, _on_http)
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(LibraryNotFoundError, _on_lib_404)
    app.add_exception_handler(LibraryAlreadyExistsError, _on_lib_conflict)
    app.add_exception_handler(CrossLibraryReferenceError, _on_xref)
    app.add_exception_handler(ConfigError, _on_config)
    app.add_exception_handler(TaskNotFoundError, _on_task_not_found)
    app.add_exception_handler(TaskHistoryExpiredError, _on_task_history_expired)
    app.add_exception_handler(QueueFullError, _on_queue_full)
    app.add_exception_handler(RKBError, _on_rkb)
    app.add_exception_handler(Exception, _on_unexpected)
