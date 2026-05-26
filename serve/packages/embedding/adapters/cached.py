"""SQLite-backed embedding cache wrapper.

Wraps any Embedder. Caches by SHA256(text + model) so changing the model
invalidates the cache automatically. The cache is the difference between
re-embedding 2000 papers every dev iteration vs paying once.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import aiosqlite

from packages.embedding.protocols import Embedder


class CachedEmbedder:
    """Embedder wrapper that caches vectors in SQLite by content hash."""

    def __init__(
        self,
        *,
        inner: Embedder,
        cache_path: Path,
        model_id: str,
    ) -> None:
        self._inner = inner
        self._cache_path = cache_path
        self._model_id = model_id
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    @property
    def dim(self) -> int:
        return self._inner.dim

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self._cache_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    vector_json TEXT NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    def _key(self, text: str) -> str:
        h = hashlib.sha256()
        h.update(self._model_id.encode("utf-8"))
        h.update(b"::")
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        await self._ensure_initialized()

        keys = [self._key(t) for t in texts]
        cached: dict[str, list[float]] = {}

        async with aiosqlite.connect(self._cache_path) as db:
            placeholders = ",".join("?" for _ in keys)
            sql = (
                f"SELECT cache_key, vector_json FROM embeddings WHERE cache_key IN ({placeholders})"
            )
            cursor = await db.execute(sql, keys)
            async for row in cursor:
                cached[row[0]] = json.loads(row[1])

        missing_indices = [i for i, k in enumerate(keys) if k not in cached]
        if missing_indices:
            missing_texts = [texts[i] for i in missing_indices]
            new_vectors = await self._inner.embed(missing_texts)

            async with aiosqlite.connect(self._cache_path) as db:
                for idx, vec in zip(missing_indices, new_vectors, strict=True):
                    cached[keys[idx]] = vec
                    await db.execute(
                        "INSERT OR REPLACE INTO embeddings(cache_key, vector_json) VALUES (?, ?)",
                        (keys[idx], json.dumps(vec)),
                    )
                await db.commit()

        return [cached[k] for k in keys]

    async def cache_stats(self) -> tuple[int, int]:
        """Return (total_cached, total_size_bytes) for diagnostics."""
        await self._ensure_initialized()
        async with aiosqlite.connect(self._cache_path) as db:
            cursor = await db.execute("SELECT COUNT(*), SUM(LENGTH(vector_json)) FROM embeddings")
            row = await cursor.fetchone()
        if row is None:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)
