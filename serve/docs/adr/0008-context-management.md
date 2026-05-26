# ADR-0008: Context Management Subsystem (M8.1–M8.3)

**Status**: Accepted
**Date**: 2026-04-30
**Drives**: M8 multi-turn conversation + research memory
**Inspired by**: Claude Code's 4-layer context architecture (Context Engine →
Compaction → Memory → Session Persistence; see `claude-code/docs/architecture-diagram/details.js`)

## Context

M7 shipped a chat-shaped UI but every turn is a fresh single-shot QA call —
backend has no notion of `Conversation` or prior turns. Real research workflows
demand follow-up ("tell me more about it"), comparison ("contrast the two"),
and refinement ("rewrite this without jargon"). Plus the user has stable
preferences across sessions ("focus on post-2023 work").

We need a context-management subsystem that:
1. Persists conversations (resume / share / fork)
2. Carries prior turns into the prompt within token budget
3. Rewrites anaphoric questions before retrieval (so retrieval still works)
4. Compacts long histories without losing critical state
5. Stores per-Library research preferences as first-class data

## Decisions

### 1. New `packages/context/` package (sibling to `orchestration/`)
Layer L4.5 — sits between L5 orchestration tasks and L4 retrieval/L1-L3
storage. Tasks consume the `ContextService` facade; everything else is private.

```
packages/context/
├── protocols.py         # Conversation / Turn / MemoryEntry / ContextBudget
├── budget.py            # ContextBudget — token counting + slot reservations
├── prompt_composer.py   # PromptComposer — layered system+library+memory+history+evidence assembly
├── compactor.py         # TurnCompactor — snip / summary / auto strategies
├── query_rewriter.py    # QueryRewriter — anaphora resolution (small LLM call)
├── memory.py            # ResearchMemory — CRUD per Library
├── conversation_repo.py # ConversationRepo — sqlite persistence
└── service.py           # ContextService — facade for tasks
```

### 2. Storage choice: sqlite (not Postgres)
Following the same pragma as `packages/ingestion/state.py` —
operator-local, simple migration story, zero new infra. When/if multi-process
worker comes, swap to Postgres behind the same `Repo` Protocol.

DB path: `Settings.context_db_path = "data/state/context.sqlite"` (separate
from `ingest.sqlite` so backups are independent).

Tables:
- `conversations(library_id, conversation_id, title, summary, created_at, updated_at)`
- `turns(conversation_id, turn_id, role, content, citations_json, rewritten_query, model, input_tokens, output_tokens, created_at)`
- `memory_entries(library_id, entry_id, kind, title, content, created_at, updated_at)`

All tables index on `library_id` for the per-Library partition rule.

### 3. Layered prompt (mirrors Claude Code's `context.ts`)
```
┌─────────────────────────────────────────┐
│ 1. Base system prompt           [fixed] │
│ 2. Library card                 [128t]  │
│ 3. Research memory (relevant)    [≤512t] │
│ 4. Compacted earlier history    [≤1024t] │
│ 5. Recent N raw turns           [≤2048t] │
│ 6. Retrieved evidence           [≤4096t] │
│ 7. Current user question        [≤512t]  │
└─────────────────────────────────────────┘
```
`ContextBudget.max_input_tokens` (default 24576 of a 32k context) budgets
each slot; the `Compactor` is invoked when `recent_turns > slot 5`.

### 4. Compaction strategies (mirrors `services/compact/`)

| Strategy | Trigger | Action |
|---|---|---|
| **snip** | Every turn submission | Drop `evidence` from old turns; keep `content + citations` |
| **summary** | When recent_turns slot would overflow | Single LLM call summarizes oldest 5 turns into a paragraph; replaces them |
| **auto** | Wraps both: hits budget → snip first, still too big → summary | The default `Compactor.fit(turns, budget)` returns `(compacted_summary: str, recent_turns: tuple[Turn,...])` |

Critically: **retrieval evidence is never persisted in turns**. We persist
the *answer + citation IDs only*; on rerender, the UI can re-fetch evidence
by chunk_id from Qdrant. This keeps the conversation table small and avoids
historical-evidence drift.

### 5. Query rewriting (anaphora resolution)
Before retrieval, every user turn after the first goes through:

```
QueryRewriter.rewrite(question, last_2_turns) -> RewriteResult{
    rewritten: str,
    confidence: float,   # cheap heuristic + LLM self-report
    used_history: bool,
}
```

Implementation: one LLM call with a tight prompt (~80 tokens in, ~40 out),
temperature=0. If `confidence < 0.6`, fall back to original. The rewritten
query is what hits `Planner.plan_and_retrieve`; the original is what the
LLM sees in slot 7 (so the user's literal phrasing is preserved in the
answer's tone).

`Settings.rewrite_enabled = True` by default; can be disabled to save
tokens during eval runs.

### 6. ResearchMemory (per Library)
Mirrors Claude Code's 4 memory kinds, retargeted to research:

| Kind | Example |
|---|---|
| `user` | "I'm a CS PhD focusing on retrieval; explain to that level" |
| `feedback` | "Always cite the original paper, never just the survey" |
| `project` | "I'm writing a NeurIPS submission on agentic retrieval" |
| `reference` | "Group's bibtex lives at git+ssh://...../refs.bib" |

CRUD is manual (M8.3 phase). Future M9: LLM auto-suggests memory entries
based on observed patterns.

In prompt slot 3, only entries with relevance > threshold to the current
question are included (cosine over their embedding vs the rewritten query).
Falls back to most-recent-first if embedding cache miss.

### 7. Conversation lifecycle
- **Create**: `POST /v1/libraries/{id}/conversations` — auto-titled from first
  question (small LLM call after first user turn)
- **Append turn**: `POST .../conversations/{cid}/turns` (or SSE streaming variant)
- **Resume**: `GET .../conversations/{cid}` — UI reloads turns; URL is shareable
- **Compact**: `POST .../conversations/{cid}/compact` (manual trigger)
- **Delete**: hard delete of conversation + turns; memory survives
- **Branch**: deferred — would need turn-tree instead of linear list

### 8. Backwards compatibility
Existing `POST /v1/libraries/{id}/qa` and `GET .../qa/stream` remain — they
operate without a `conversation_id` (single-shot). New `conversations` API
is additive. Frontend defaults to creating a fresh conversation per page
load when none in URL.

## Consequences

- One new package (`packages/context/`) — modest, ~600 lines
- One new sqlite DB file (`data/state/context.sqlite`)
- 6 new HTTP endpoints (conversations × 5 + memory × 4)
- QATask gains an optional `conversation_id` parameter; non-conversation
  callers are unaffected
- Token cost increases per turn after the first (~80 tokens for rewrite +
  N tokens for compacted summary); evaluable via the existing
  `rag_llm_tokens_total` metric
- Frontend gains a left sidebar listing past conversations (familiar mental
  model from ChatGPT / Claude Code)
- ResearchMemory becomes the first-class place to encode a researcher's
  long-running preferences without re-typing them every session

## Non-goals

- **Multi-user / sharing**: out of scope for v1 (single-tenant). Shareable
  URLs work within one user's installation.
- **Conversation forking / turn-tree**: deferred to M9 if needed.
- **LLM-driven memory auto-extraction**: deferred — manual entry first.
- **Cross-Library context**: explicitly rejected (per ADR-0003 isolation
  rule); each conversation is bound to one library_id at creation.

## Implementation milestones

| Milestone | Deliverable | Estimated effort |
|---|---|---|
| **M8.1** Skeleton | protocols + repo + composer + service + 5 conversation API endpoints; QATask plumbed; basic UI sidebar | 1–2 days |
| **M8.2** Compaction + rewriting | TurnCompactor + QueryRewriter + auto-trigger | 1 day |
| **M8.3** ResearchMemory | memory.py + 4 memory API endpoints + UI memory drawer | 1 day |

Total: ~3–4 days; all three implemented in parallel via 7 agents per the
file-partition table in this commit.

## References

- Claude Code: `claude-code/docs/architecture-diagram/details.js` —
  `context_engine`, `compact_system`, `memory_system`, `session_system`
- ADR-0003: Library as data partition (informs per-Library scoping)
- M7 ingest_state precedent: `packages/ingestion/state.py` (sqlite-as-state)
