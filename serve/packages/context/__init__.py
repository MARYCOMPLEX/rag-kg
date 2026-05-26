"""Context management subsystem (M8).

Provides Conversation / Turn persistence, layered prompt assembly,
compaction, query rewriting, and ResearchMemory CRUD. See ADR-0008.

Public surface:
- Data models: `Conversation`, `Turn`, `MemoryEntry`, `ContextBudget`
- Service facade: `ContextService` (used by orchestration tasks)
- Building blocks (advanced use): `PromptComposer`, `TurnCompactor`,
  `QueryRewriter`, `ResearchMemory`, `ConversationRepo`
"""

from packages.context.protocols import (
    ContextBudget,
    Conversation,
    MemoryEntry,
    MemoryKind,
    Turn,
    TurnRole,
)

__all__ = [
    "ContextBudget",
    "Conversation",
    "MemoryEntry",
    "MemoryKind",
    "Turn",
    "TurnRole",
]
