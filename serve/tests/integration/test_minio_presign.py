"""Integration test for the MinIO presigned-GET adapter.

ADR_REVIEW §11.3 follow-up. The test runs in two modes:

1. **Live MinIO** — when ``MINIO_TEST_ENDPOINT`` is set we point at a
   real server, upload a tiny PDF object, presign it, and assert the
   resulting URL serves the same bytes via plain HTTP GET. This is the
   contract the API route ultimately depends on.
2. **Smoke (unconditional)** — input validation guards: empty IDs raise
   ``ValueError`` without touching MinIO.

The MinIO Python SDK contacts the server during ``presigned_get_object``
to discover the bucket region, so the live path requires a reachable
endpoint. We do *not* run that path by default to keep CI infra-free.
"""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import io
import os

import httpx
import pytest

from apps._shared.factories.minio_presign import (
    MinioPresigner,
    MinioPresignerConfig,
)

_LIBRARY_ID = "test-lib"
_DOC_ID = "doc-1"
_FILE_NAME = "sample.pdf"
_PDF_BYTES = b"%PDF-1.4\n%fake-pdf-for-presign-test"


def _from_env() -> MinioPresignerConfig | None:
    endpoint = os.environ.get("MINIO_TEST_ENDPOINT")
    if not endpoint:
        return None
    return MinioPresignerConfig(
        endpoint=endpoint,
        access_key=os.environ.get("MINIO_TEST_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("MINIO_TEST_SECRET_KEY", "minioadmin"),
        bucket=os.environ.get("MINIO_TEST_BUCKET", "kb-test"),
        secure=os.environ.get("MINIO_TEST_SECURE", "0") == "1",
    )


def _ensure_bucket_and_upload(presigner: MinioPresigner, key: str) -> None:
    """Ensure the bucket exists and put a tiny PDF object at ``key``."""
    client = presigner._client
    bucket = presigner._config.bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(_PDF_BYTES),
        length=len(_PDF_BYTES),
        content_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_presign_get_returns_url_to_uploaded_object() -> None:
    """Live test — only runs when MINIO_TEST_ENDPOINT points at a server.

    Asserts the presigned URL fetches the exact bytes we uploaded.
    """
    config = _from_env()
    if config is None:
        pytest.skip("MINIO_TEST_ENDPOINT not set; skipping live presign test")

    presigner = MinioPresigner(config)
    key = f"{_LIBRARY_ID}/{_DOC_ID}/{_FILE_NAME}"
    _ensure_bucket_and_upload(presigner, key)

    url = await presigner.presign_get(
        library_id=_LIBRARY_ID,
        doc_id=_DOC_ID,
        file_name=_FILE_NAME,
        ttl_s=300,
    )

    assert url.startswith(("http://", "https://"))
    assert _LIBRARY_ID in url
    assert _DOC_ID in url

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    assert resp.status_code == 200
    assert resp.content == _PDF_BYTES


@pytest.mark.asyncio
async def test_presign_get_rejects_empty_ids() -> None:
    """Validation guard runs before any MinIO I/O.

    Empty ``library_id`` / ``doc_id`` must produce a ``ValueError``
    rather than a misleading network error.
    """
    presigner = MinioPresigner(
        MinioPresignerConfig(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="kb-test",
        )
    )

    with pytest.raises(ValueError, match="library_id and doc_id are required"):
        await presigner.presign_get(
            library_id="",
            doc_id=_DOC_ID,
            ttl_s=60,
            file_name=_FILE_NAME,
        )

    with pytest.raises(ValueError, match="library_id and doc_id are required"):
        await presigner.presign_get(
            library_id=_LIBRARY_ID,
            doc_id="",
            ttl_s=60,
            file_name=_FILE_NAME,
        )
