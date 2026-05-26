"""Factory wiring for cross-app DI containers (CLI + API + Worker)."""

from apps._shared.factories.builders import AppContainer, build_container
from apps._shared.factories.community_runner import (
    CommunityRebuildResult,
    rebuild_communities,
)
from apps._shared.factories.ingest_runner import IngestResult, ingest_pdf

__all__ = [
    "AppContainer",
    "CommunityRebuildResult",
    "IngestResult",
    "build_container",
    "ingest_pdf",
    "rebuild_communities",
]
