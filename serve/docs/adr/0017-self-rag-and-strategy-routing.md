# ADR-0017: Self-RAG / CRAG / ToG Implementation Path and Strategy Routing

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §3.3 Gap 2; PRD §11.2 (M4 Agentic Retrieval Scope) and §11.5 (M4 Exit Criteria)
**Related**: ADR-0001 (modular monolith), ADR-0007 (SSE), ADR-0009 (task queue + RetrievalBudget plumbing), ADR-0010 (stage_progress events), ADR-0015 (daily cost cap), ADR-0018 (reranker selection)

## Context

PRD §11.2 (M4 — Agentic Retrieval) names four retrieval strategies as in-scope:

- **ReActPlanner** — basic Thought / Action / Observation loop.
- **SelfRAGStyleCritic** — prompt-based reflection that does not modify the LLM
  vocabulary, simulating the four reflection-token roles from Asai et al. 2024.
- **CRAGEvaluator** — lightweight evaluator (small LLM judge or cross-encoder
  threshold) that triggers re-retrieval when evidence quality is poor.
- **ToGPlanner** — KG beam search with depth ≤ 3 and beam ≤ 4, all graph
  queries scoped to a single `library_id`.

Today only `packages/retrieval/strategies/react_rag.py` is implemented.
BACKEND_ROADMAP §3.3 Gap 2 calls out the missing trio — `self_rag_critic.py`,
`crag_evaluator.py`, `tog_planner.py` — and notes that the API contract
(`POST /v1/libraries/{lib}/qa`) must accept
`strategy: "react" | "self_rag" | "crag" | "tog" | "auto"`.

PRD §11.5 sets a hard exit gate of **Citation F1 ≥ 0.85** on the 30-question
multihop set. ReAct alone has been measured at ~0.78 on the smoke set; the gap
is real and the missing strategies must close it without exploding cost
(PRD §11.6 lists "LLM cost spike" as a top risk, mitigated by the budget gate).

### Forces

- **No fine-tuning of the base LLM.** Project policy (rules/coding-style + memory
  `feedback_cost.md`) forbids LLM training. The Self-RAG paper's reflection
  tokens (`[Retrieve]`, `[IsRel]`, `[IsSup]`, `[IsUse]`) live in a fine-tuned
  vocabulary; we cannot use them as-is.
- **No new GPU surface.** The reranker (ADR-0018) already loads BGE-reranker-v2.
  Asking for a second cross-encoder for CRAG would double GPU memory on the
  worker box. Reuse is mandatory.
- **`library_id` is everywhere.** Every Protocol's first non-self argument is
  the library id (PRD §16.6 discipline). Strategies are not exempt.
- **Cost is observable.** Each strategy's LLM/embedding spend lands in
  Langfuse and accumulates against the per-Library daily cap (ADR-0015).
  Self-RAG's reflection step roughly doubles LLM calls per turn — the budget
  must understand this or the user gets surprised by 2× spend.
- **Auto-selection must exist.** PRD §11.2 lists `strategy=auto` as the
  default; we cannot ship four strategies with no router.

## Decision

We adopt a **prompt-based Self-RAG critic, a cross-encoder CRAG evaluator that
reuses the BGE-reranker-v2 model from ADR-0018, and a KG-beam-search ToG
planner**, all behind a single `RetrievalStrategy` Protocol. A lightweight
heuristic router maps `strategy=auto` to one of the four planners based on the
question type and the active `RetrievalBudget`.

### 1. `RetrievalStrategy` Protocol contract

The Protocol lives in `packages/retrieval/strategies/__init__.py` and is the
single seam for orchestration. Every strategy takes `library_id` as the first
argument (per PRD §16.6) and returns a `RetrievalTrace` whose evidence is also
library-scoped.

```python
# packages/retrieval/strategies/__init__.py
from typing import Protocol

from packages.core.models import (
    Query,
    RetrievalBudget,
    RetrievalTrace,
)


class RetrievalStrategy(Protocol):
    name: str  # "react" | "self_rag" | "crag" | "tog"

    async def run(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalTrace: ...
```

`RetrievalTrace` already carries `library_id`, ordered `steps`,
`final_evidence`, `budget_used`, and `terminated_reason` (PRD §11.4). No model
changes are required for the Protocol; new strategies write into the same trace
shape so `apps/web` does not branch on planner.

### 2. Self-RAG: prompt-based reflection (rejected: fine-tuning)

We **simulate the four reflection-token roles via prompts**, never via vocab
extension. Each role is a separate structured-output call to the LLM gateway.

| Role         | Prompt purpose                                                               | Output shape                   |
|--------------|------------------------------------------------------------------------------|--------------------------------|
| `Retrieve`   | Decide whether retrieval is needed for the current sub-question              | `{"retrieve": bool, "why": str}` |
| `IsRel`      | Score each candidate chunk's relevance to the sub-question                   | `{"chunk_id": str, "rel": "rel"|"partial"|"no"}` |
| `IsSup`      | Decide whether the draft answer is supported by the cited evidence           | `{"supported": "full"|"partial"|"no", "reason": str}` |
| `IsUse`      | Score the answer's overall usefulness against the original question          | `{"usefulness": 1..5, "reason": str}` |

Pseudocode for the loop (lives in `packages/retrieval/strategies/self_rag_critic.py`):

```python
async def run(self, library_id, query, budget):
    trace = RetrievalTrace.empty(library_id)
    sub_qs = await self._decompose(query)            # uses rewriter.decompose
    for sub_q in sub_qs:
        if budget.exhausted():
            break
        retrieve = await self._reflect_retrieve(sub_q)
        if not retrieve.retrieve:
            continue                                 # skip retrieval, answer directly
        candidates = await self._coordinator.search(library_id, sub_q, k=20)
        scored = await self._reflect_is_rel(sub_q, candidates)
        kept = [c for c in scored if c.rel != "no"]
        draft = await self._draft_answer(sub_q, kept)
        sup = await self._reflect_is_sup(draft, kept)
        if sup.supported == "no" and budget.can_retry():
            # one round of re-retrieval with rewritten query
            sub_q2 = await self._rewriter.step_back(sub_q)
            candidates2 = await self._coordinator.search(library_id, sub_q2, k=20)
            scored2 = await self._reflect_is_rel(sub_q2, candidates2)
            kept = kept + [c for c in scored2 if c.rel == "rel"]
            draft = await self._draft_answer(sub_q, kept)
        trace.append_step(sub_q, kept, draft)
    final = await self._synthesize(trace.steps)
    use = await self._reflect_is_use(query, final)
    trace.finalize(final, use)
    return trace
```

Two structural rules are non-negotiable:

- **Hard step cap.** `budget.max_steps` (default 8 — see PRD §11.4) terminates
  the loop. Every reflection round counts as one step. The loop sets
  `terminated_reason="budget_exceeded"` rather than silently truncating.
- **Reflection cost is real cost.** Each of the four reflection roles is one
  structured-output LLM call. The Self-RAG planner reports its budget consumption
  in `budget_used.llm_calls` and `budget_used.tokens`, which feeds straight into
  ADR-0015's daily cap.

### 3. CRAG: cross-encoder evaluator (rejected: small-LLM judge)

CRAG (Yan et al. 2024) calls for a "retrieval evaluator" that decides whether
the retrieved set is good (use as-is), ambiguous (search the open web — out of
scope for v1), or bad (decompose and re-retrieve from corpus). We implement
**only the corpus path** in v1.

Evaluator: **reuse the BGE-reranker-v2 cross-encoder loaded for ADR-0018.**
Score each `(query, chunk)` pair, take `max_score` and `mean_top_k`, and bucket
into three confidence levels by static thresholds:

```python
# packages/retrieval/strategies/crag_evaluator.py
HIGH_THRESHOLD = 0.70   # top-1 above → trust
LOW_THRESHOLD  = 0.30   # max below   → reject and rewrite

class CRAGEvaluator:
    async def evaluate(
        self, library_id: str, query: str, candidates: list[RetrievedEvidence]
    ) -> Literal["confident", "ambiguous", "incorrect"]:
        if not candidates:
            return "incorrect"
        scores = await self._reranker.score(query, [c.chunk.text for c in candidates])
        top1 = max(scores)
        topk = sorted(scores, reverse=True)[:5]
        mean_top5 = sum(topk) / len(topk)
        if top1 >= HIGH_THRESHOLD:
            return "confident"
        if top1 < LOW_THRESHOLD or mean_top5 < LOW_THRESHOLD:
            return "incorrect"
        return "ambiguous"
```

`incorrect` and `ambiguous` both trigger one round of `decompose + re-retrieve`
through `packages/retrieval/rewriter.py`. We **do not** call the open web —
that's deferred to M8.

**Why cross-encoder, not small-LLM judge.** A 2-billion-parameter LLM judge
runs ~400 ms/call and costs LLM tokens; the BGE-reranker scores 30 candidates
in ~120 ms with no token cost (model is already in GPU memory for ADR-0018).
The judging signal is also cleaner: judge LLMs are known to overweight
fluency over factuality, which is the opposite of what CRAG wants.

**Joint scoring with reranker.** When CRAG runs, the cross-encoder forward
pass produces scores that the coordinator can also use to re-order candidates.
We pass the score tensor through to `HybridRetrievalCoordinator` so the
reranker call is **shared between CRAG evaluation and final ranking** —
budget impact is one inference pass, not two. ADR-0018 §6 commits to the
matching API.

### 4. ToG: KG beam search

ToG (Sun et al. 2024) walks the KG outward from question entities, scoring
partial paths by LLM relevance, until budget runs out or the answer is
producible. We implement a constrained version:

- **Entity seeding**: NER on the question (GLiNER, already loaded in M2);
  seed entities are matched to KG nodes via the existing EntityLinker. All
  seeds must be in `library_id`'s graph.
- **Beam search**: depth ≤ 3, beam ≤ 4, branching factor ≤ 8. Per step, we
  expand each beam's leaf node by one hop in Neo4j, then call one LLM round
  to score `(path → relevance)` and keep the top `beam` paths.
- **Termination**: stop when (a) any beam path's evidence answers the question
  per a structured-output check, (b) `max_llm_calls` is hit, or (c) depth = 3.

```cypher
// packages/indexing/graph_index.py — beam expansion query (one hop)
MATCH (n {library_id: $library_id, id: $head_id})-[r]-(m {library_id: $library_id})
WHERE r.confidence >= $min_conf
RETURN m.id AS tail_id, type(r) AS rel, r.confidence AS conf
LIMIT $branching_factor
```

The `library_id` constraint on **both** match patterns is mandatory (PRD §9
KG isolation, ADR-0003). Cross-Library traversal is a v2 feature.

### 5. Auto-router: question-type heuristic

`strategy=auto` runs a small classifier over the question (cached, no GPU) and
maps to a planner. The classifier is a 3-feature rule, not an ML model:

| Feature                              | Source                              |
|--------------------------------------|-------------------------------------|
| `is_multihop`                        | LLM structured call: "is this a multi-hop question?" — 1 call, cached by query hash for 24 h |
| `entity_count`                       | NER hits on the question            |
| `is_global` (whole-corpus question)  | Existing M3 router (ADR-0006)       |

```python
# packages/retrieval/strategy_router.py
def select_strategy(query, budget) -> str:
    if budget.max_llm_calls < 10:
        return "react"                      # cheap floor
    if is_global(query):
        return "react"                      # community routing handles globals
    if entity_count(query) >= 2 and is_multihop(query):
        return "tog"                        # multi-hop with named entities → ToG
    if budget.max_llm_calls >= 20 and is_multihop(query):
        return "self_rag"                   # multi-hop, can afford reflection
    return "crag"                           # ambiguous / long-tail → CRAG fallback
```

Budget interaction is intentional: when the per-Library daily cap (ADR-0015)
is near the warn line, the router downshifts to ReAct. The router's decision
is logged into `RetrievalTrace.steps[0].thought` so the auto-selection is
auditable from the UI's reasoning panel.

### 6. SSE event emission

Each planner emits `stage_progress` events (ADR-0010) at strategy-specific
boundaries:

| Planner    | Stages emitted                                                            |
|------------|---------------------------------------------------------------------------|
| `react`    | `react.iter` (one per Thought/Action/Observation)                         |
| `self_rag` | `self_rag.decompose`, `self_rag.retrieve`, `self_rag.is_rel`, `self_rag.draft`, `self_rag.is_sup`, `self_rag.is_use` |
| `crag`     | `crag.evaluate`, `crag.rewrite`, `crag.re_retrieve`                       |
| `tog`      | `tog.seed`, `tog.expand[depth=N]`, `tog.score`, `tog.synthesize`          |

`stage_progress.payload` carries `{current, total}` so the frontend can render
the Reasoning Trace inline (BACKEND_ROADMAP §3.3 Gap 1).

### 7. Evaluation discipline

PRD §11.5 sets the citation gate; we add per-strategy reporting so the gate is
strategy-aware. The evaluator (M6) writes a row per `(eval_set, strategy)`:

```python
# packages/evaluation/strategy_report.py
class StrategyReport(BaseModel):
    library_id: str
    eval_set: str                  # "smoke" | "multihop" | "global"
    strategy: str                  # "react" | "self_rag" | "crag" | "tog" | "auto"
    recall_at_10: float
    citation_f1: float
    avg_cost_usd: Decimal
    avg_latency_s: float
    n_questions: int
    timestamp: datetime
```

A new planner cannot be promoted to `auto` until it equals or beats ReAct on
**all three** axes (recall, F1, cost-bounded). This is the M4 §11.6 risk
mitigation made operational.

## Consequences

### Positive

- **Correctness**: Self-RAG's IsSup gate measurably reduces hallucinated
  citations; the M4 exit criterion (Citation F1 ≥ 0.85) becomes reachable.
- **Safety net**: CRAG catches the long-tail case where vector + BM25 + graph
  all return junk; the alternative is a confident-sounding wrong answer.
- **Reach**: ToG produces structured paths the S7 Reason screen can render
  directly (BACKEND_ROADMAP §3.7 Gap 1's `ReasoningPath` model is filled by
  ToG output).
- **Cost discipline**: per-strategy reports + auto-router downshift on
  near-cap budgets means cost rises gradually, not in a step.
- **Reuse**: zero new model artifacts. CRAG shares the reranker; Self-RAG
  shares the chat LLM; ToG shares the Neo4j adapter.

### Negative

- **2× LLM calls on Self-RAG path.** A reflection-heavy question can spend
  10–14 LLM calls. Mitigated by budget caps and the `is_multihop` gate in the
  router (we don't pay for reflection on simple questions).
- **CRAG threshold is a magic constant.** `HIGH_THRESHOLD=0.70` and
  `LOW_THRESHOLD=0.30` are calibrated on a 50-question sample; recalibration
  requires re-running the calibration set when the reranker version changes
  (tracked as a small task in `packages/evaluation/calibrate_crag.py`).
- **ToG depth=3 is a ceiling, not a floor.** Some 4-hop questions in research
  literature won't fit. We accept this in v1 because ToG cost grows
  combinatorially with depth and our budget would explode.
- **Auto-router is rule-based.** It will misclassify edge cases. Mitigation:
  the user can always pin `strategy=` explicitly from the Composer
  (BACKEND_ROADMAP §3.3 prototype already exposes a Strategy pill).

### Risks

| Risk                                           | Mitigation                                                                 |
|------------------------------------------------|----------------------------------------------------------------------------|
| Self-RAG reflection loop fails to terminate    | Hard `max_steps` + `terminated_reason="budget_exceeded"` returns partial answer with banner |
| CRAG and reranker share GPU memory under load  | Single forward pass shared between CRAG eval and final rerank; jobs queue serially per worker process |
| ToG beam explosion on hub entities             | `branching_factor` cap + `min_confidence` filter on edges; hub detection at expansion time skips degree-200+ nodes |
| Auto-router locks into a bad strategy on a Library | Per-strategy report + manual override pill; eval CI gates strategy promotion |
| Reflection prompts drift LLM provider behavior | Structured output + Pydantic parse + one-retry fallback (already in `packages/llm/gateway.py`) |

## Alternatives Considered

| Option                                          | Rejected Because                                                                                          |
|-------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| **Fine-tuned Self-RAG (Asai 2024 original)**    | Requires labeled reflection-token data we don't have; iteration cycle (collect → train → eval) is weeks; project mandate is no-LLM-training (memory `feedback_cost.md`); we are not an LLM lab |
| **Small-LLM judge for CRAG (e.g. Haiku-as-judge)** | 4× the cost of a cross-encoder pass; judge LLMs reward fluency over factuality; defeats the purpose       |
| **Single-strategy ensemble (run all 4, vote)**  | 4× LLM spend per question; budget cap (ADR-0015) blocks this for any production Library                  |
| **No router, force user to pick strategy**      | UX regression vs PRD §11.2 default (`strategy=auto`); most users won't know which planner fits           |
| **MIPRO / DSPy program-search**                 | Adds a meta-optimizer dependency and a separate calibration corpus; v2 candidate, not M4                 |
| **Pure ToG (drop ReAct/Self-RAG/CRAG)**         | Fails on entity-light questions; KG coverage is uneven across Libraries                                  |

## Open Questions

1. **Calibration cadence for CRAG thresholds.** Currently expected to refresh
   per Library on its smoke set; should this be automated by a
   `calibrate_crag` worker job (ADR-0009 task type)? *Decision deferred to
   first M4-to-M6 retro.*
2. **Should `strategy=auto` cache its decision per-conversation?** Switching
   strategies mid-conversation may confuse users. Provisional answer: cache
   for the conversation lifetime, allow per-turn override.
3. **Should ToG paths be persisted as `ReasoningPath` rows in Postgres?**
   Required for the S7 history UX but adds write load; deferred to ADR-0020.
4. **Multilingual reflection prompts.** PRD §17 R02 covers parser fallback;
   reflection prompt fallback is not yet covered. Plan: same fallback-chain
   pattern as parsers, deferred until a non-English Library exists.

## Relationships With Other ADRs

- **ADR-0001 (Modular Monolith)** — All planners live in
  `packages/retrieval/strategies/`. Their boundaries match the import-graph
  rules (`tach`); coordinator depends on strategies, never the reverse.
- **ADR-0007 (Error Envelope + SSE)** — `RetrievalTrace` errors map to the
  `RKBError` family and surface through the unified envelope; budget-exceeded
  is `code=BUDGET_EXCEEDED` with the partial trace in `details.trace`.
- **ADR-0009 (Async Task Queue)** — Long-running QA tasks can elect to run
  through the queue; `RetrievalBudget.timeout_s` becomes the worker timeout.
- **ADR-0010 (SSE Stage Events)** — Each planner emits `stage_progress` per
  the table in §6 above. The event stream is the single source of truth for
  the inline reasoning panel.
- **ADR-0015 (Daily Cost Cap)** — Self-RAG's reflection step doubles call
  counts. Auto-router downshifts to ReAct when daily spend ≥ 80% of cap;
  ≥ 100% blocks new tasks. The router checks `library_daily_cost` before
  promoting `auto` to anything cost-heavy.
- **ADR-0018 (Reranker Selection)** — CRAG reuses the reranker model; the
  joint-scoring API is specified there. Without ADR-0018 this ADR cannot
  ship as written.
- **ADR-0006 (Local vs Global Routing)** — Auto-router defers to the
  local/global router for whole-corpus questions; community routing is not
  duplicated here.

## References

- PRD §11.2 (M4 Scope), §11.4 (data models), §11.5 (exit criteria),
  §11.6 (risks)
- BACKEND_ROADMAP §3.3 Gap 2 (file plan), §3.3 Gap 3 (RRF/Rerank coupling),
  §2.1 (RetrievalBudget origin), §5 (ADR-0017 line item)
- Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique
  through Self-Reflection," 2024 — reflection-token vocabulary
- Yan et al., "Corrective Retrieval Augmented Generation," 2024 —
  evaluator categories (confident/ambiguous/incorrect)
- Sun et al., "Think-on-Graph: Deep and Responsible Reasoning of Large
  Language Model on Knowledge Graph," 2024 — beam search formulation
- `packages/retrieval/strategies/react_rag.py` — existing baseline
- `packages/retrieval/rewriter.py` — HyDE / Step-Back / decompose helpers
  shared across strategies
