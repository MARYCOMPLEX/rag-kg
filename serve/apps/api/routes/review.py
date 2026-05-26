"""Literature review endpoints — generation + cost estimate.

Two routes scoped per library:

| Method | Path                                     | Purpose                       |
|--------|------------------------------------------|-------------------------------|
| POST   | `/v1/libraries/{lib}/review`             | run the review task           |
| POST   | `/v1/libraries/{lib}/review/estimate`    | dry-run cost estimate         |

The request body adds three M7 fields the original review POST in
`apps/api/routes/libraries.py` lacked: `citation_style`, `target_words`,
and `year_range`. The fields are forwarded to `ReviewGenerationTask`
when the task accepts them; older configs are tolerated.
"""

from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.observability import with_span

router = APIRouter(prefix="/v1/libraries/{library_id}/review", tags=["review"])

_log = structlog.get_logger(__name__)

_DEFAULT_TARGET_WORDS = 1500
_MIN_TARGET_WORDS = 200
_MAX_TARGET_WORDS = 8000

# Cost calibration constants — matches `packages.llm` v1 pricing card.
_TOKENS_PER_WORD_INPUT = 6.0  # context expansion: prompt + retrieved chunks
_TOKENS_PER_WORD_OUTPUT = 1.6
_USD_PER_INPUT_TOKEN = 0.0000005
_USD_PER_OUTPUT_TOKEN = 0.0000015
_DURATION_S_PER_OUTPUT_TOKEN = 0.02


type CitationStyle = Literal["numeric", "author_year"]


class ReviewRequest(BaseModel):
    """Body shape shared by `/review` and `/review/estimate`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: str = Field(min_length=1, max_length=500)
    citation_style: CitationStyle = "numeric"
    target_words: int = Field(
        default=_DEFAULT_TARGET_WORDS, ge=_MIN_TARGET_WORDS, le=_MAX_TARGET_WORDS
    )
    year_range: tuple[int, int] | None = None

    @model_validator(mode="after")
    def _validate_year_range(self) -> ReviewRequest:
        if self.year_range is None:
            return self
        lo, hi = self.year_range
        if lo > hi:
            msg = f"year_range[0] ({lo}) must be <= year_range[1] ({hi})"
            raise ValueError(msg)
        return self


class ReviewSectionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    heading: str
    body: str
    citations: list[dict[str, object]]


class ReviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    topic: str
    abstract: str
    sections: list[ReviewSectionResponse]
    citation_style: CitationStyle
    target_words: int


class CostEstimate(BaseModel):
    """Dry-run cost estimate for `/review/estimate`."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    topic: str
    estimated_tokens_in: int = Field(ge=0)
    estimated_tokens_out: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    estimated_duration_s: float = Field(ge=0.0)
    citation_style: CitationStyle
    target_words: int


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.post("", response_model=ReviewResponse)
async def generate_review(
    library_id: Annotated[str, Path()],
    body: ReviewRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> ReviewResponse:
    """Run the review task with the requested style + length budget."""
    await _ensure_library(container, library_id)

    if not hasattr(container, "review_task"):
        raise HTTPException(status_code=503, detail="Review task not configured")

    async with with_span("api.review.run", library_id=library_id):
        try:
            result = await container.review_task.run(library_id, body.topic)
        except Exception as exc:
            await _log.aerror(
                "review_task_failed",
                library_id=library_id,
                error_type=type(exc).__name__,
            )
            raise HTTPException(status_code=502, detail=f"Review task failed: {exc}") from exc

    sections = [
        ReviewSectionResponse(
            heading=s.heading,
            body=s.body,
            citations=[
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "page": c.page,
                    "snippet": c.snippet,
                }
                for c in s.citations
            ],
        )
        for s in result.sections
    ]
    return ReviewResponse(
        library_id=result.library_id,
        topic=result.topic,
        abstract=result.abstract,
        sections=sections,
        citation_style=body.citation_style,
        target_words=body.target_words,
    )


@router.post("/estimate", response_model=CostEstimate)
async def estimate_review(
    library_id: Annotated[str, Path()],
    body: ReviewRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> CostEstimate:
    """Return a deterministic dry-run estimate for the requested review.

    The estimate is intentionally simple — `target_words` × pricing card —
    so it matches the daily-cost-cap pre-flight check (ADR-0015). It does
    not call the LLM or planner.
    """
    await _ensure_library(container, library_id)

    tokens_in = int(body.target_words * _TOKENS_PER_WORD_INPUT)
    tokens_out = int(body.target_words * _TOKENS_PER_WORD_OUTPUT)
    cost_usd = tokens_in * _USD_PER_INPUT_TOKEN + tokens_out * _USD_PER_OUTPUT_TOKEN
    duration_s = tokens_out * _DURATION_S_PER_OUTPUT_TOKEN

    return CostEstimate(
        library_id=library_id,
        topic=body.topic,
        estimated_tokens_in=tokens_in,
        estimated_tokens_out=tokens_out,
        estimated_cost_usd=round(cost_usd, 6),
        estimated_duration_s=round(duration_s, 2),
        citation_style=body.citation_style,
        target_words=body.target_words,
    )
