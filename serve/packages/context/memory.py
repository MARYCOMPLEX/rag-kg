"""ResearchMemory + sqlite store for the context subsystem (ADR-0008 §6).

`SqliteMemoryStore` persists `MemoryEntry` rows in a single sqlite database
keyed by `(library_id, entry_id)`. The schema is created on first use and
all operations are guarded by a `threading.Lock` so the same instance is
safe to share across asyncio tasks (mirrors `packages/ingestion/state.py`).

`ResearchMemory` is the high-level facade tasks consume: it wraps any
`MemoryStore` Protocol implementation and adds CRUD ergonomics, a relevance
selector, and a compact prompt-block renderer.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from packages.context.protocols import (
    MemoryEntry,
    MemoryKind,
    MemoryStore,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    library_id  TEXT NOT NULL,
    entry_id    TEXT NOT NULL,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (library_id, entry_id)
);
CREATE INDEX IF NOT EXISTS ix_memory_library ON memory_entries(library_id);
"""

# Default cap for entries surfaced into a prompt block. The wrapper accepts an
# override per-call; this default is also configurable via Settings.
_DEFAULT_PROMPT_CAP = 5

# How many chars of `content` we render inline before truncating with an
# ellipsis. Keep this tight — full content lives in storage; the prompt only
# needs a recall hint.
_RENDER_CONTENT_CHARS = 240

# Kinds that should always be preferred when selecting relevant entries —
# `user`/`feedback` reflect explicit researcher preferences, while
# `project`/`reference` are background context that may matter less per turn.
_PRIORITY_KINDS: frozenset[MemoryKind] = frozenset({"user", "feedback"})

# Valid kinds derived from the Protocol Literal so we validate at boundaries
# without re-declaring the union.
_VALID_KINDS: frozenset[str] = frozenset(get_args(MemoryKind))


def _parse_iso(text: str) -> datetime:
    """Parse an ISO-8601 string back into a tz-aware datetime."""
    return datetime.fromisoformat(text)


class SqliteMemoryStore:
    """Thread-safe sqlite-backed `MemoryStore` implementation.

    The connection is opened with `check_same_thread=False` and every call
    site grabs `self._lock` before touching the connection — concurrent
    asyncio tasks running on a single thread are safe, and incidental
    cross-thread use is also fine. Async methods wrap blocking sqlite
    operations directly: per ADR-0008 the volume is low (single-digit reads
    and writes per turn) so we avoid the complexity of `aiosqlite`.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    async def list_entries(self, library_id: str, *, limit: int = 200) -> tuple[MemoryEntry, ...]:
        """List entries for a library, newest-updated first.

        Thread-safe via lock; sqlite call is sync.
        """
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT library_id, entry_id, kind, title, content, created_at, updated_at
                FROM memory_entries
                WHERE library_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (library_id, int(limit)),
            )
            rows = cur.fetchall()
        return tuple(_row_to_entry(r) for r in rows)

    async def get_entry(self, library_id: str, entry_id: str) -> MemoryEntry | None:
        """Fetch a single entry; returns None when missing.

        Thread-safe via lock; sqlite call is sync.
        """
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT library_id, entry_id, kind, title, content, created_at, updated_at
                FROM memory_entries
                WHERE library_id = ? AND entry_id = ?
                """,
                (library_id, entry_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_entry(row)

    async def upsert_entry(self, entry: MemoryEntry) -> None:
        """Insert or replace an entry by `(library_id, entry_id)`.

        Pre-existing rows keep their `created_at` (we honor whatever value
        the caller supplied on `entry.created_at`, since `MemoryEntry` is
        frozen — `ResearchMemory.update` is the right place to preserve it).

        Thread-safe via lock; sqlite call is sync.
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_entries (
                    library_id, entry_id, kind, title, content, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_id, entry_id) DO UPDATE SET
                    kind=excluded.kind,
                    title=excluded.title,
                    content=excluded.content,
                    updated_at=excluded.updated_at
                """,
                (
                    entry.library_id,
                    entry.entry_id,
                    entry.kind,
                    entry.title,
                    entry.content,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )
            self._conn.commit()

    async def delete_entry(self, library_id: str, entry_id: str) -> None:
        """Delete an entry; silent no-op if missing.

        Thread-safe via lock; sqlite call is sync.
        """
        with self._lock:
            self._conn.execute(
                "DELETE FROM memory_entries WHERE library_id = ? AND entry_id = ?",
                (library_id, entry_id),
            )
            self._conn.commit()

    async def close(self) -> None:
        """Close the underlying sqlite connection."""
        with self._lock:
            self._conn.close()


def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    """Map a sqlite row to the frozen `MemoryEntry` Pydantic model."""
    return MemoryEntry(
        library_id=row["library_id"],
        entry_id=row["entry_id"],
        kind=row["kind"],
        title=row["title"],
        content=row["content"],
        created_at=_parse_iso(row["created_at"]),
        updated_at=_parse_iso(row["updated_at"]),
    )


class ResearchMemory:
    """High-level wrapper over a `MemoryStore` Protocol.

    Provides CRUD ergonomics, a relevance selector for prompt-time use, and
    a compact text renderer. Stateless apart from the injected store and a
    cap on how many entries to surface into the prompt.
    """

    def __init__(
        self,
        *,
        store: MemoryStore,
        max_entries_in_prompt: int = _DEFAULT_PROMPT_CAP,
    ) -> None:
        self._store = store
        self._cap = max(0, int(max_entries_in_prompt))

    async def list(self, library_id: str) -> tuple[MemoryEntry, ...]:
        """Return all entries for a library, newest-updated first."""
        return await self._store.list_entries(library_id)

    async def select_relevant(
        self,
        library_id: str,
        query: str,
        *,
        limit: int | None = None,
    ) -> tuple[MemoryEntry, ...]:
        """Pick the most relevant entries for a query.

        Heuristic-only for now: prefer `user`/`feedback` kinds, break ties
        by lexical token overlap with `query`, then by `updated_at` desc.

        # TODO(M9): replace with cosine over entry embeddings cached in Qdrant
        """
        entries = await self._store.list_entries(library_id)
        if not entries:
            return ()

        cap = self._cap if limit is None else max(0, int(limit))
        if cap == 0:
            return ()

        target_count = min(cap, len(entries))
        query_tokens = _tokenize(query)
        ranked = sorted(
            entries,
            key=lambda e: _relevance_key(e, query_tokens),
            reverse=True,
        )
        return tuple(ranked[:target_count])

    async def render_block(self, entries: tuple[MemoryEntry, ...]) -> str:
        """Render entries as compact markdown bullets for prompt inclusion.

        Returns `""` when `entries` is empty, with no leading or trailing
        whitespace in either case.
        """
        if not entries:
            return ""
        lines = [_render_entry_line(e) for e in entries]
        return "\n".join(lines)

    async def create(
        self,
        library_id: str,
        kind: MemoryKind,
        title: str,
        content: str,
    ) -> MemoryEntry:
        """Create a new entry with a fresh `entry_id` and timestamps."""
        _validate_kind(kind)
        now = datetime.now(tz=UTC)
        entry = MemoryEntry(
            library_id=library_id,
            entry_id=uuid.uuid4().hex[:16],
            kind=kind,
            title=title,
            content=content,
            created_at=now,
            updated_at=now,
        )
        await self._store.upsert_entry(entry)
        return entry

    async def update(
        self,
        library_id: str,
        entry_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        kind: MemoryKind | None = None,
    ) -> MemoryEntry | None:
        """Patch a stored entry; returns the updated copy, or None if missing."""
        existing = await self._store.get_entry(library_id, entry_id)
        if existing is None:
            return None
        if kind is not None:
            _validate_kind(kind)
        updates: dict[str, object] = {"updated_at": datetime.now(tz=UTC)}
        if title is not None:
            updates["title"] = title
        if content is not None:
            updates["content"] = content
        if kind is not None:
            updates["kind"] = kind
        updated = existing.model_copy(update=updates)
        await self._store.upsert_entry(updated)
        return updated

    async def delete(self, library_id: str, entry_id: str) -> None:
        """Delete an entry; idempotent."""
        await self._store.delete_entry(library_id, entry_id)


def _render_entry_line(entry: MemoryEntry) -> str:
    """Render one entry as `- [kind] title: content` with content truncated."""
    content = entry.content
    if len(content) > _RENDER_CONTENT_CHARS:
        content = content[:_RENDER_CONTENT_CHARS].rstrip() + "..."
    return f"- [{entry.kind}] {entry.title}: {content}"


def _tokenize(text: str) -> frozenset[str]:
    """Lowercase whitespace-split tokens; punctuation kept attached.

    Cheap and dependency-free — good enough for tiebreaker overlap counting
    until M9 swaps in real embeddings.
    """
    return frozenset(t for t in text.lower().split() if t)


def _relevance_key(entry: MemoryEntry, query_tokens: frozenset[str]) -> tuple[int, int, str]:
    """Sort key: (kind_priority, lexical_overlap, updated_at_iso).

    Higher tuples sort first under `reverse=True`. Using the ISO timestamp
    string as a final tiebreaker is safe because ISO-8601 sorts
    lexicographically the same way it sorts chronologically.
    """
    kind_priority = 1 if entry.kind in _PRIORITY_KINDS else 0
    if query_tokens:
        entry_tokens = _tokenize(f"{entry.title} {entry.content}")
        overlap = len(query_tokens & entry_tokens)
    else:
        overlap = 0
    return (kind_priority, overlap, entry.updated_at.isoformat())


def _validate_kind(kind: str) -> None:
    """Raise `ValueError` if `kind` is not a recognized `MemoryKind`."""
    if kind not in _VALID_KINDS:
        raise ValueError(f"invalid memory kind: {kind!r}")
