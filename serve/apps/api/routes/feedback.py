"""User-feedback endpoints (ADR-0016 §2).

Two routes scoped under a single ``answer_id``:

| Method | Path                                                          |
|--------|---------------------------------------------------------------|
| POST   | ``/v1/libraries/{lib}/qa/{answer_id}/feedback``                |
| DELETE | ``/v1/libraries/{lib}/qa/{answer_id}/feedback``                |

The ``(answer_id, user_id)`` UNIQUE constraint on the ``answer_feedback``
table guarantees idempotency: re-posting with the same Principal updates
the verdict instead of creating a duplicate (ADR-0016 §R-VAR-2 spam guard).
DELETE is a soft-revoke — the row stays for audit, only ``revoked_at``
is stamped.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._eval_deps import get_feedback_store
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.eval_models import AnswerFeedback
from packages.orchestration.eval_protocols import FeedbackStore

router = APIRouter(
    prefix="/v1/libraries/{library_id}/qa/{answer_id}/feedback",
    tags=["feedback"],
)


_LIB_DESC = "Library slug"
_ANSWER_DESC = "ULID returned by the original /qa response"
_COMMENT_MAX = 2000


class FeedbackRequest(BaseModel):
    """Body for ``POST .../feedback``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    useful: bool
    citations_correct: bool
    comment: str | None = Field(default=None, max_length=_COMMENT_MAX)


class FeedbackResponse(BaseModel):
    """Echo shape returned on submit (201 Created)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    answer_id: str
    user_id: str | None
    useful: bool
    citations_correct: bool
    comment: str | None
    created_at: datetime
    revoked_at: datetime | None


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit user feedback for an answer",
)
async def submit_feedback(
    body: FeedbackRequest,
    library_id: str = Path(..., description=_LIB_DESC),
    answer_id: str = Path(..., description=_ANSWER_DESC),
    container: AppContainer = Depends(get_container),
    store: FeedbackStore = Depends(get_feedback_store),
    principal: Principal = Depends(get_current_principal),
) -> FeedbackResponse:
    await _ensure_library(container, library_id)
    user_id = _user_id_or_none(principal)
    now = datetime.now(UTC)
    feedback = AnswerFeedback(
        library_id=library_id,
        answer_id=answer_id,
        user_id=user_id,
        useful=body.useful,
        citations_correct=body.citations_correct,
        comment=body.comment,
        created_at=now,
        revoked_at=None,
    )
    await store.submit(feedback)
    return FeedbackResponse(
        library_id=feedback.library_id,
        answer_id=feedback.answer_id,
        user_id=feedback.user_id,
        useful=feedback.useful,
        citations_correct=feedback.citations_correct,
        comment=feedback.comment,
        created_at=feedback.created_at,
        revoked_at=feedback.revoked_at,
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke previously-submitted feedback (soft delete)",
)
async def revoke_feedback(
    library_id: str = Path(..., description=_LIB_DESC),
    answer_id: str = Path(..., description=_ANSWER_DESC),
    container: AppContainer = Depends(get_container),
    store: FeedbackStore = Depends(get_feedback_store),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    await _ensure_library(container, library_id)
    await store.revoke(library_id, answer_id, _user_id_or_none(principal))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _user_id_or_none(principal: Principal) -> str | None:
    """Anonymous principals collapse to NULL so the UNIQUE pair stays
    well-defined per (answer_id, NULL) → at most one anonymous row."""
    if principal.kind == "anonymous":
        return None
    return principal.id


__all__ = ["router"]
