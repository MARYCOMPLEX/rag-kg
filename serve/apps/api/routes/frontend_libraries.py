"""Frontend-facing library endpoints under `/api/libraries`.

The existing `/v1/libraries` routes expose backend domain fields such as
`library_id`. This adapter preserves those routes and maps repository data
into the field names currently consumed by the Vue frontend.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import make_library
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.library_admin import init_library
from packages.core.models import LIBRARY_ID_PATTERN, Language, Library, LibraryStatus

router = APIRouter(prefix="/api/libraries", tags=["libraries"])
logger = logging.getLogger(__name__)

_LIBRARY_ID_RE = re.compile(LIBRARY_ID_PATTERN)

type FrontendLibraryAccent = Literal["concept", "method", "dataset", "citation", "author"]
type FrontendLibraryStatus = Literal["healthy", "indexing"]
type FrontendLibraryLanguage = Literal["en", "zh", "multi"]

_ACCENTS: tuple[FrontendLibraryAccent, ...] = (
    "concept",
    "method",
    "dataset",
    "citation",
    "author",
)


class FrontendLibrarySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    name: str
    document_count_label: str = Field(alias="documentCountLabel")
    chunk_count_label: str = Field(alias="chunkCountLabel")
    entity_count_label: str = Field(alias="entityCountLabel")
    activity_label: str = Field(alias="activityLabel")
    status_label: str = Field(alias="statusLabel")
    status: FrontendLibraryStatus
    accent: FrontendLibraryAccent
    featured: bool | None = None


class FrontendLibraryCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=3, max_length=31)
    description: str = Field(max_length=2000)
    language: FrontendLibraryLanguage
    template: str = Field(min_length=1, max_length=100)


class FrontendLibraryCreateResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library: FrontendLibrarySummary
    redirect_to: str = Field(alias="redirectTo")


def _accent_for(library_id: str) -> FrontendLibraryAccent:
    digest = hashlib.sha1(library_id.encode("utf-8")).digest()[0]
    return _ACCENTS[digest % len(_ACCENTS)]


def _frontend_status(status_value: LibraryStatus) -> FrontendLibraryStatus:
    if status_value is LibraryStatus.HEALTHY:
        return "healthy"
    return "indexing"


def _status_label(status_value: FrontendLibraryStatus) -> str:
    if status_value == "healthy":
        return "Healthy"
    return "Indexing"


def _language_to_backend(language: FrontendLibraryLanguage) -> Language:
    if language == "multi":
        return "mixed"
    return language


def _summary_from_library(library: Library) -> FrontendLibrarySummary:
    frontend_status = _frontend_status(library.status)
    return FrontendLibrarySummary(
        id=library.library_id,
        name=library.name,
        documentCountLabel="0 documents",
        chunkCountLabel="0 chunks",
        entityCountLabel="0 entities",
        activityLabel=f"Created {library.created_at.date().isoformat()}",
        statusLabel=_status_label(frontend_status),
        status=frontend_status,
        accent=_accent_for(library.library_id),
    )


@router.get(
    "",
    response_model=list[FrontendLibrarySummary],
    response_model_exclude_none=True,
)
async def list_frontend_libraries(
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> list[FrontendLibrarySummary]:
    libraries = await container.library_repo.list_all()
    return [_summary_from_library(library) for library in libraries]


@router.post(
    "",
    response_model=FrontendLibraryCreateResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_frontend_library(
    body: FrontendLibraryCreateRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendLibraryCreateResponse:
    if not _LIBRARY_ID_RE.match(body.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid slug '{body.slug}'. Must match pattern: "
                "lowercase, start with letter, 3-31 chars, only [a-z0-9-]."
            ),
        )

    library = make_library(
        library_id=body.slug,
        name=body.name,
        description=body.description,
        language=_language_to_backend(body.language),
    )
    await container.library_repo.create(library)
    try:
        await init_library(body.slug, adapters=[container.vector_index])
    except Exception:
        logger.warning(
            "Frontend library metadata created but resource initialization failed",
            extra={"library_id": body.slug},
            exc_info=True,
        )
    return FrontendLibraryCreateResponse(
        library=_summary_from_library(library),
        redirectTo=f"/libraries/{body.slug}/docs?onboarding=1",
    )
