"""HTTP request/response Pydantic schemas (API layer).

These models live separate from the domain models in `packages/*/models.py`
per CODING_STANDARDS §13.1: API schemas float with the wire contract,
domain models float with the business semantics.
"""

from apps.api.schemas.activity import ActivityEventResponse, ActivityListResponse
from apps.api.schemas.documents import (
    DocumentChunkResponse,
    DocumentChunksListResponse,
    DocumentDetailResponse,
    DocumentPdfUrlResponse,
    DocumentRetryResponse,
    DocumentSectionResponse,
    DocumentSummaryResponse,
)
from apps.api.schemas.notifications import (
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationResponse,
)
from apps.api.schemas.purge import (
    LibraryPurgeReceiptResponse,
    LibraryPurgeResponse,
    LibraryStatsResponseV2,
)
from apps.api.schemas.search import SearchHitResponse, SearchResponse
from apps.api.schemas.settings import (
    DailyCostEntry,
    EmbedderSpecPayload,
    LibraryCostResponse,
    LibrarySettingsPatchRequest,
    LibrarySettingsResponse,
    LLMRouterSpecPayload,
    RerankerSpecPayload,
    RetrievalBudgetPayload,
)

__all__ = [
    "ActivityEventResponse",
    "ActivityListResponse",
    "DailyCostEntry",
    "DocumentChunkResponse",
    "DocumentChunksListResponse",
    "DocumentDetailResponse",
    "DocumentPdfUrlResponse",
    "DocumentRetryResponse",
    "DocumentSectionResponse",
    "DocumentSummaryResponse",
    "EmbedderSpecPayload",
    "LLMRouterSpecPayload",
    "LibraryCostResponse",
    "LibraryPurgeReceiptResponse",
    "LibraryPurgeResponse",
    "LibrarySettingsPatchRequest",
    "LibrarySettingsResponse",
    "LibraryStatsResponseV2",
    "NotificationListResponse",
    "NotificationMarkReadResponse",
    "NotificationResponse",
    "RerankerSpecPayload",
    "RetrievalBudgetPayload",
    "SearchHitResponse",
    "SearchResponse",
]
