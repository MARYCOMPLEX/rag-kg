"""MinIO presigned-GET URL helper for the document detail drawer.

Wraps the official ``minio`` Python SDK so the API route in
``apps/api/routes/documents.py`` can ask the DI container for a
short-lived presigned URL without touching the SDK directly.

Object key layout (matches the document upload pipeline):

    <library_id>/<doc_id>/<file_name>

The actual upload is handled elsewhere (ingest pipeline); this helper
is read-only.

Why a thin wrapper rather than a full storage adapter:

- Only a single read use case exists today (``GET /v1/.../docs/{doc_id}/pdf``).
- Adding a full ``ObjectStore`` Protocol now would be premature — we'll
  promote this to ``packages/<storage>`` when a second consumer (e.g.
  attachment download) appears (YAGNI per CODING_STANDARDS).
- Lives under ``apps/_shared/factories`` because the only call sites are
  the FastAPI DI container and worker job seam.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from urllib.parse import quote

import structlog
from minio import Minio

from packages.core.config import Settings

_log = structlog.get_logger(__name__)

#: Hard cap on the presigned URL TTL. MinIO's documented maximum is
#: 7 days; we keep a generous internal ceiling and let the API route
#: choose a much shorter TTL (5 min) per ADR_REVIEW §4.
_MAX_TTL_S: Final[int] = 7 * 24 * 3600


@dataclass(frozen=True, slots=True)
class MinioPresignerConfig:
    """Configuration for ``MinioPresigner``."""

    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False


def _safe_object_key(library_id: str, doc_id: str, file_name: str) -> str:
    """Build the canonical object key for a document.

    Uses URL-quoted file name so spaces and unicode characters survive
    the round trip through the MinIO HTTP API.
    """
    safe_name = quote(file_name, safe="._-")
    return f"{library_id}/{doc_id}/{safe_name}"


class MinioPresigner:
    """Async-friendly facade over ``minio.Minio.presigned_get_object``.

    The MinIO SDK is synchronous; we offload to a thread so the FastAPI
    event loop is never blocked. A single ``Minio`` instance is reused
    (it is thread-safe for read operations per upstream docs).
    """

    def __init__(self, config: MinioPresignerConfig) -> None:
        self._config = config
        self._client = Minio(
            endpoint=config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )

    async def presign_get(
        self,
        *,
        library_id: str,
        doc_id: str,
        ttl_s: int,
        file_name: str | None = None,
    ) -> str:
        """Return a presigned GET URL for the canonical PDF object.

        Args:
            library_id: Library partition.
            doc_id: Document identifier within the library.
            ttl_s: TTL in seconds. Clamped to ``[1, _MAX_TTL_S]``.
            file_name: Optional original upload file name. When omitted,
                the first object under ``<library_id>/<doc_id>/`` is
                resolved by listing the prefix — the upload pipeline
                guarantees a single PDF per ``doc_id``.

        Returns:
            The presigned URL as a ``str``. Raises ``FileNotFoundError``
            when no file_name was supplied and the prefix is empty;
            re-raises ``minio`` errors otherwise.
        """
        if not library_id or not doc_id:
            msg = "library_id and doc_id are required"
            raise ValueError(msg)

        clamped_ttl = max(1, min(ttl_s, _MAX_TTL_S))
        bucket = self._config.bucket
        key = await self._resolve_object_key(library_id, doc_id, file_name)

        def _call() -> str:
            return self._client.presigned_get_object(
                bucket_name=bucket,
                object_name=key,
                expires=timedelta(seconds=clamped_ttl),
            )

        try:
            return await asyncio.to_thread(_call)
        except Exception as exc:
            await _log.awarning(
                "minio_presign_failed",
                bucket=bucket,
                key=key,
                error_type=type(exc).__name__,
            )
            raise

    async def _resolve_object_key(
        self,
        library_id: str,
        doc_id: str,
        file_name: str | None,
    ) -> str:
        """Resolve the storage key, falling back to a prefix list."""
        if file_name:
            return _safe_object_key(library_id, doc_id, file_name)

        prefix = f"{library_id}/{doc_id}/"
        bucket = self._config.bucket

        def _list_first() -> str | None:
            for obj in self._client.list_objects(bucket, prefix=prefix, recursive=True):
                name = obj.object_name
                if name:
                    return name
            return None

        first = await asyncio.to_thread(_list_first)
        if first is None:
            msg = f"No object found under prefix '{prefix}' in bucket '{bucket}'"
            raise FileNotFoundError(msg)
        return first


def build_minio_presigner(settings: Settings) -> MinioPresigner:
    """Construct a ``MinioPresigner`` from application Settings."""
    return MinioPresigner(
        MinioPresignerConfig(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
        )
    )


__all__ = [
    "MinioPresigner",
    "MinioPresignerConfig",
    "build_minio_presigner",
]
