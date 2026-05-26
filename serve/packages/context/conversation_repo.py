"""Sqlite-backed `ConversationStore` implementation.

Mirrors the conventions used by `packages/ingestion/state.py`:

* one connection per store, guarded by a `threading.Lock`
* `check_same_thread=False` so async callers on different worker threads
  can share the connection
* `PRAGMA foreign_keys=ON` so deleting a conversation cascades to its turns
* parametrized SQL only — no string concatenation
* every async method wraps the blocking sqlite work under the lock; we
  intentionally do not push to a thread-pool because the per-call work
  is microseconds and an `asyncio.to_thread` round-trip would dominate.

Citations are persisted as a JSON array of Pydantic-serialized objects via
`Citation.model_dump_json` so the on-disk format is forward-compatible with
schema additions to `Citation`.

See ADR-0008 §2 for the storage decision and table layout.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from packages.context.protocols import (
    Conversation,
    Turn,
    TurnRole,
)
from packages.orchestration.protocols import Citation

_SCHEMA_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    library_id      TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (library_id, conversation_id)
)
"""

# A standalone UNIQUE index on conversation_id is required so the turns FK
# below can reference it. (SQLite requires the FK target to be either the
# PK or UNIQUE; the composite PK is not addressable by a single-col FK.)
# Conversation ids are uuid4 hex prefixes — globally unique by construction.
_INDEX_CONV_ID_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_conv_id ON conversations(conversation_id)
"""

_INDEX_CONVERSATIONS = """
CREATE INDEX IF NOT EXISTS ix_conv_library
    ON conversations(library_id, updated_at DESC)
"""

_SCHEMA_TURNS = """
CREATE TABLE IF NOT EXISTS turns (
    conversation_id TEXT NOT NULL,
    turn_id         TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content         TEXT NOT NULL DEFAULT '',
    citations_json  TEXT NOT NULL DEFAULT '[]',
    rewritten_query TEXT,
    model           TEXT,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (conversation_id, turn_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        ON DELETE CASCADE
)
"""

_INDEX_TURNS = """
CREATE INDEX IF NOT EXISTS ix_turns_conv
    ON turns(conversation_id, created_at)
"""


def _serialize_citations(citations: tuple[Citation, ...]) -> str:
    """Serialize a tuple of Citations as a JSON array string.

    Each item is `Citation.model_dump_json` so we round-trip through Pydantic
    rather than hand-rolled dict mapping; this makes us forward-compatible
    with new optional fields on `Citation`.
    """
    return json.dumps([c.model_dump(mode="json") for c in citations])


def _deserialize_citations(blob: str) -> tuple[Citation, ...]:
    """Reconstruct citations from the persisted JSON array."""
    if not blob:
        return ()
    raw: object = json.loads(blob)
    if not isinstance(raw, list):
        return ()
    items = cast(list[Any], raw)
    return tuple(Citation.model_validate(item) for item in items)


def _row_to_conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        library_id=row["library_id"],
        conversation_id=row["conversation_id"],
        title=row["title"] or "",
        summary=row["summary"] or "",
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_turn(row: sqlite3.Row) -> Turn:
    role_value = row["role"]
    if role_value not in ("user", "assistant"):
        raise ValueError(f"unexpected role in db: {role_value!r}")
    role: TurnRole = role_value
    return Turn(
        conversation_id=row["conversation_id"],
        turn_id=row["turn_id"],
        role=role,
        content=row["content"] or "",
        citations=_deserialize_citations(row["citations_json"] or "[]"),
        rewritten_query=row["rewritten_query"],
        model=row["model"],
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class SqliteConversationRepo:
    """Thread-safe sqlite-backed `ConversationStore` implementation.

    Implements the `ConversationStore` Protocol structurally — no inheritance.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute(_SCHEMA_CONVERSATIONS)
        self._conn.execute(_INDEX_CONV_ID_UNIQUE)
        self._conn.execute(_INDEX_CONVERSATIONS)
        self._conn.execute(_SCHEMA_TURNS)
        self._conn.execute(_INDEX_TURNS)
        self._conn.commit()

    async def create_conversation(self, conversation: Conversation) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO conversations (
                    library_id, conversation_id, title, summary,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.library_id,
                    conversation.conversation_id,
                    conversation.title,
                    conversation.summary,
                    conversation.created_at.isoformat(),
                    conversation.updated_at.isoformat(),
                ),
            )
            self._conn.commit()

    async def get_conversation(self, library_id: str, conversation_id: str) -> Conversation | None:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT * FROM conversations
                WHERE library_id = ? AND conversation_id = ?
                """,
                (library_id, conversation_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _row_to_conversation(row)

    async def list_conversations(
        self, library_id: str, *, limit: int = 50
    ) -> tuple[Conversation, ...]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT * FROM conversations
                WHERE library_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (library_id, limit),
            )
            rows = cur.fetchall()
        return tuple(_row_to_conversation(r) for r in rows)

    async def update_conversation(self, conversation: Conversation) -> None:
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE conversations
                SET title = ?, summary = ?, updated_at = ?
                WHERE library_id = ? AND conversation_id = ?
                """,
                (
                    conversation.title,
                    conversation.summary,
                    conversation.updated_at.isoformat(),
                    conversation.library_id,
                    conversation.conversation_id,
                ),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                raise ValueError(
                    f"conversation {conversation.conversation_id} not found "
                    f"in {conversation.library_id}"
                )

    async def delete_conversation(self, library_id: str, conversation_id: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                DELETE FROM conversations
                WHERE library_id = ? AND conversation_id = ?
                """,
                (library_id, conversation_id),
            )
            self._conn.commit()

    async def append_turn(self, turn: Turn) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO turns (
                    conversation_id, turn_id, role, content,
                    citations_json, rewritten_query, model,
                    input_tokens, output_tokens, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.conversation_id,
                    turn.turn_id,
                    turn.role,
                    turn.content,
                    _serialize_citations(turn.citations),
                    turn.rewritten_query,
                    turn.model,
                    turn.input_tokens,
                    turn.output_tokens,
                    turn.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    async def list_turns(self, conversation_id: str, *, limit: int = 200) -> tuple[Turn, ...]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT * FROM turns
                WHERE conversation_id = ?
                ORDER BY created_at ASC, turn_id ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
            rows = cur.fetchall()
        return tuple(_row_to_turn(r) for r in rows)

    async def close(self) -> None:
        with self._lock:
            self._conn.close()
