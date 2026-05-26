"""Public data models + Protocols for the context subsystem.

Every model is `frozen=True, extra="forbid"` per the project standards.
`library_id` is the first field on every Library-scoped model.

Implementations (PromptComposer, TurnCompactor, QueryRewriter, ResearchMemory,
ConversationRepo, ContextService) live in sibling modules and are imported
lazily by callers — keeping protocols.py free of LLM/storage dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.orchestration.protocols import Citation

TurnRole = Literal["user", "assistant"]
MemoryKind = Literal["user", "feedback", "project", "reference"]


class Turn(BaseModel):
    """A single turn in a conversation. Citations are by-reference (chunk_id only)
    so we never duplicate retrieval evidence into conversation storage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conversation_id: str = Field(min_length=1, max_length=64)
    turn_id: str = Field(min_length=1, max_length=64)
    role: TurnRole
    content: str = ""
    citations: tuple[Citation, ...] = ()
    rewritten_query: str | None = None
    model: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    created_at: datetime


class Conversation(BaseModel):
    """A library-scoped conversation. The `summary` slot is populated lazily
    by the compactor; the title is auto-derived from the first user turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1, max_length=63)
    conversation_id: str = Field(min_length=1, max_length=64)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=8000)
    created_at: datetime
    updated_at: datetime


class MemoryEntry(BaseModel):
    """One entry in the ResearchMemory store. Unlike `Turn`, memory is
    long-lived and survives conversation deletion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1, max_length=63)
    entry_id: str = Field(min_length=1, max_length=64)
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=8000)
    created_at: datetime
    updated_at: datetime


class ContextBudget(BaseModel):
    """Token budget for the layered prompt assembly. Slot allocations are
    advisory — the composer enforces total ≤ max_input_tokens by trimming the
    LOWEST-priority slots first (history before evidence before memory before
    library_card)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_input_tokens: int = Field(default=24576, ge=512)
    library_card_max: int = Field(default=128, ge=0)
    memory_max: int = Field(default=512, ge=0)
    summary_max: int = Field(default=1024, ge=0)
    recent_turns_max: int = Field(default=2048, ge=0)
    evidence_max: int = Field(default=4096, ge=0)
    user_question_max: int = Field(default=512, ge=0)


class RewriteResult(BaseModel):
    """Output of the query rewriter — keeps the original alongside the
    rewritten so downstream code can pick which to show in the answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original: str
    rewritten: str
    confidence: float = Field(ge=0.0, le=1.0)
    used_history: bool = False


class ComposedPrompt(BaseModel):
    """The PromptComposer's output: ready-to-send messages plus a token
    accounting summary so callers can record observability without
    re-counting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system: str
    user: str
    estimated_input_tokens: int = Field(ge=0)
    slots_used: dict[str, int]


# === Protocols (structural typing — implementations live elsewhere) ===


@runtime_checkable
class TokenCounter(Protocol):
    """Adapter for token counting. Tasks inject their own; the default
    implementation in `budget.py` uses a fast char/4 heuristic."""

    def count(self, text: str) -> int: ...


@runtime_checkable
class ConversationStore(Protocol):
    """Persistence Protocol — sqlite implementation is the default."""

    async def create_conversation(self, conversation: Conversation) -> None: ...
    async def get_conversation(
        self, library_id: str, conversation_id: str
    ) -> Conversation | None: ...
    async def list_conversations(
        self, library_id: str, *, limit: int = 50
    ) -> tuple[Conversation, ...]: ...
    async def update_conversation(self, conversation: Conversation) -> None: ...
    async def delete_conversation(self, library_id: str, conversation_id: str) -> None: ...

    async def append_turn(self, turn: Turn) -> None: ...
    async def list_turns(self, conversation_id: str, *, limit: int = 200) -> tuple[Turn, ...]: ...

    async def close(self) -> None: ...


@runtime_checkable
class MemoryStore(Protocol):
    """Persistence Protocol for ResearchMemory — sqlite by default."""

    async def list_entries(
        self, library_id: str, *, limit: int = 200
    ) -> tuple[MemoryEntry, ...]: ...
    async def get_entry(self, library_id: str, entry_id: str) -> MemoryEntry | None: ...
    async def upsert_entry(self, entry: MemoryEntry) -> None: ...
    async def delete_entry(self, library_id: str, entry_id: str) -> None: ...
    async def close(self) -> None: ...
