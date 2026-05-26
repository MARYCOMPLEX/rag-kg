"""Unified error envelope shared by API and CLI surfaces.

`ErrorCode` is the wire-stable enum the frontend `ApiError` switches on.
`ErrorEnvelope` is the JSON body returned for any non-2xx HTTP response.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ErrorCode(StrEnum):
    """Stable, machine-readable error categories."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    NOT_FOUND = "NOT_FOUND"
    LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND"
    LIBRARY_ALREADY_EXISTS = "LIBRARY_ALREADY_EXISTS"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorEnvelope(BaseModel):
    """Wire shape for every error response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ErrorCode
    message: str
    request_id: str
    details: object | None = None
