"""`ContextService` — high-level facade orchestration tasks consume.

This is the *only* surface tasks need to know about. Everything else
(`PromptComposer`, `TurnCompactor`, `QueryRewriter`, `ResearchMemory`) is
optional and injected by builders when those modules land. The facade
deliberately avoids importing those modules so this file is importable
even mid-rollout.

Responsibilities:
    * conversation lifecycle (open / list / delete)
    * turn append (user / assistant) with token accounting
    * summary + title updates (immutable: returns the new `Conversation`)
    * pass-through `history` and `list` for callers that just need data

All mutations use `Conversation.model_copy(update=...)` so the returned
object is a fresh frozen instance — callers should drop the old reference.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from packages.context.protocols import (
    Conversation,
    ConversationStore,
    MemoryStore,
    Turn,
)
from packages.orchestration.protocols import Citation

_CONV_ID_LEN = 16
_TURN_ID_LEN = 16


def _new_id(length: int) -> str:
    """Return a hex token of the requested length, sourced from uuid4."""
    return uuid.uuid4().hex[:length]


def _utcnow() -> datetime:
    """Timezone-aware UTC now — frozen models reject naive datetimes."""
    return datetime.now(tz=UTC)


class ContextService:
    """Composition-only facade over `ConversationStore` (+ optional memory).

    Optional dependencies (compactor / query rewriter / prompt composer / memory)
    are injected via constructor kwargs by `apps/_shared/factories/builders.py`
    once the relevant modules land. Until then, the facade exposes only the
    storage-level API which is everything M8.A5 needs.
    """

    def __init__(
        self,
        *,
        store: ConversationStore,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._store = store
        self._memory_store = memory_store

    @property
    def memory_store(self) -> MemoryStore | None:
        """The injected memory store, if any. Read-only."""
        return self._memory_store

    async def open(
        self,
        *,
        library_id: str,
        conversation_id: str | None = None,
        autocreate_title: str = "",
    ) -> Conversation:
        """Open an existing conversation or create a fresh one.

        Args:
            library_id: The owning library's id (per ADR-0003 isolation).
            conversation_id: If provided, fetch and return; raise if missing.
                If None, create a new conversation with a generated id.
            autocreate_title: Initial title for newly-created conversations.
                Ignored when `conversation_id` is provided.

        Raises:
            ValueError: When `conversation_id` is provided but no row exists.
        """
        if conversation_id is None:
            return await self._create_fresh(library_id=library_id, title=autocreate_title)

        existing = await self._store.get_conversation(library_id, conversation_id)
        if existing is None:
            raise ValueError(f"conversation {conversation_id} not found in {library_id}")
        return existing

    async def _create_fresh(self, *, library_id: str, title: str) -> Conversation:
        now = _utcnow()
        conv = Conversation(
            library_id=library_id,
            conversation_id=_new_id(_CONV_ID_LEN),
            title=title,
            summary="",
            created_at=now,
            updated_at=now,
        )
        await self._store.create_conversation(conv)
        return conv

    async def list(self, library_id: str, *, limit: int = 50) -> tuple[Conversation, ...]:
        """List conversations for a library, newest-updated first."""
        return await self._store.list_conversations(library_id, limit=limit)

    async def history(self, conversation_id: str, *, limit: int = 200) -> tuple[Turn, ...]:
        """Return all turns of a conversation in chronological order."""
        return await self._store.list_turns(conversation_id, limit=limit)

    async def append_user_turn(
        self,
        *,
        conversation: Conversation,
        content: str,
        rewritten_query: str | None = None,
    ) -> Turn:
        """Append a `role='user'` turn to the conversation.

        The conversation's `updated_at` is *not* bumped here — the typical
        flow appends user + assistant turns back-to-back, and the assistant
        append is what triggers the timestamp bump (see `append_assistant_turn`).
        """
        turn = Turn(
            conversation_id=conversation.conversation_id,
            turn_id=_new_id(_TURN_ID_LEN),
            role="user",
            content=content,
            citations=(),
            rewritten_query=rewritten_query,
            model=None,
            input_tokens=0,
            output_tokens=0,
            created_at=_utcnow(),
        )
        await self._store.append_turn(turn)
        return turn

    async def append_assistant_turn(
        self,
        *,
        conversation: Conversation,
        content: str,
        citations: tuple[Citation, ...],
        model: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> Turn:
        """Append a `role='assistant'` turn with citations + token accounting."""
        turn = Turn(
            conversation_id=conversation.conversation_id,
            turn_id=_new_id(_TURN_ID_LEN),
            role="assistant",
            content=content,
            citations=citations,
            rewritten_query=None,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            created_at=_utcnow(),
        )
        await self._store.append_turn(turn)
        return turn

    async def update_summary(self, *, conversation: Conversation, summary: str) -> Conversation:
        """Persist a new compactor-derived summary; returns a fresh `Conversation`."""
        updated = conversation.model_copy(update={"summary": summary, "updated_at": _utcnow()})
        await self._store.update_conversation(updated)
        return updated

    async def update_title(self, *, conversation: Conversation, title: str) -> Conversation:
        """Persist a new title; returns a fresh `Conversation`."""
        updated = conversation.model_copy(update={"title": title, "updated_at": _utcnow()})
        await self._store.update_conversation(updated)
        return updated

    async def delete(self, library_id: str, conversation_id: str) -> None:
        """Hard-delete a conversation (turns cascade via FK)."""
        await self._store.delete_conversation(library_id, conversation_id)

    async def aclose(self) -> None:
        """Close all underlying stores. Idempotent at the store level."""
        await self._store.close()
        if self._memory_store is not None:
            await self._memory_store.close()
