"""OpenSearch-backed BM25 sparse keyword index.

One index per library: bm25_<library_id>. Init creates the index with
a custom analyzer (lowercase + standard tokenizer + ASCII folding).
Library purge = DELETE index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from opensearchpy import AsyncHttpConnection, AsyncOpenSearch

from packages.core.models import Chunk
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import RETRIEVAL_DURATION_SECONDS


@dataclass(frozen=True, slots=True)
class OpenSearchBM25Config:
    """OpenSearch connection settings."""

    url: str = "http://localhost:9200"


def _index_name(library_id: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", library_id.lower())
    return f"bm25_{safe}"


_INDEX_BODY = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "similarity": {"default": {"type": "BM25", "b": 0.75, "k1": 1.2}},
        },
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "library_id": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "text": {"type": "text"},
            "page": {"type": "integer"},
            "section": {"type": "keyword"},
            "kind": {"type": "keyword"},
            "offset_start": {"type": "integer"},
            "offset_end": {"type": "integer"},
        }
    },
}


class OpenSearchBM25Index:
    """BM25 sparse index per library."""

    def __init__(self, config: OpenSearchBM25Config) -> None:
        self._config = config
        self._client = AsyncOpenSearch(
            hosts=[config.url],
            connection_class=AsyncHttpConnection,
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

    async def init_library(self, library_id: str) -> None:
        name = _index_name(library_id)
        if await self._client.indices.exists(index=name):
            return
        await self._client.indices.create(index=name, body=_INDEX_BODY)

    async def purge_library(self, library_id: str) -> None:
        name = _index_name(library_id)
        if await self._client.indices.exists(index=name):
            await self._client.indices.delete(index=name)

    @instrumented(
        op_name="bm25.upsert",
        component="bm25",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "bm25", "op": "upsert"},
        label_from_arg={"library_id": "library_id"},
    )
    async def upsert(self, library_id: str, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        name = _index_name(library_id)
        body: list[dict[str, object]] = []
        for c in chunks:
            body.append({"index": {"_index": name, "_id": c.chunk_id}})
            body.append(
                {
                    "library_id": c.library_id,
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "text": c.text,
                    "page": c.page,
                    "section": c.section,
                    "kind": c.kind,
                    "offset_start": c.offset[0],
                    "offset_end": c.offset[1],
                }
            )
        await self._client.bulk(body=body)
        await self._client.indices.refresh(index=name)

    @instrumented(
        op_name="bm25.search",
        component="bm25",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "bm25", "op": "search"},
        label_from_arg={"library_id": "library_id"},
    )
    async def search(
        self,
        library_id: str,
        query: str,
        k: int,
    ) -> list[tuple[Chunk, float]]:
        name = _index_name(library_id)
        if not await self._client.indices.exists(index=name):
            return []

        body = {
            "size": k,
            "query": {"match": {"text": {"query": query}}},
        }
        result = await self._client.search(index=name, body=body)
        out: list[tuple[Chunk, float]] = []
        for hit in result.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            try:
                chunk = Chunk(
                    library_id=str(src["library_id"]),
                    chunk_id=str(src["chunk_id"]),
                    doc_id=str(src["doc_id"]),
                    text=str(src["text"]),
                    page=int(src["page"]) if src.get("page") is not None else None,
                    section=src.get("section") if src.get("section") else None,
                    kind=str(src.get("kind", "text")),  # type: ignore[arg-type]
                    offset=(
                        int(src.get("offset_start", 0) or 0),
                        int(src.get("offset_end", 0) or 0),
                    ),
                )
            except (KeyError, ValueError, TypeError):
                continue
            out.append((chunk, float(hit.get("_score", 0.0))))
        return out

    async def close(self) -> None:
        await self._client.close()
