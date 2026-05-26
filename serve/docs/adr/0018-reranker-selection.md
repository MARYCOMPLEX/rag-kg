# ADR-0018: Reranker Selection — BGE-reranker-v2 with Cohere Fallback

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §3.3 Gap 3; PRD §9.2 (M2 RerankerService) and §9.6 (M2 Exit Criteria)
**Related**: ADR-0001 (modular monolith), ADR-0003 (library partition), ADR-0017 (Self-RAG / CRAG / ToG strategies that reuse the reranker), ADR-0015 (daily cost cap)

## Context

`packages/indexing/coordinator.py` (`HybridRetrievalCoordinator`) currently
runs vector / BM25 / graph routes serially and concatenates results. There is
**no rerank phase** and no Reciprocal Rank Fusion. The symptom: low-quality
candidates ride the rank list to the top and the M2 exit gate
(`Citation F1 ≥ 0.80`, PRD §9.6) is missed by ~5 percentage points on the
multihop set. PRD §9.2 explicitly named `RerankerService: BGE-reranker-v2
adapter (library 无关)` as in-scope for M2; we deferred during M2 because the
GPU pipeline wasn't ready, and the deferral has now blocked M4 (per
BACKEND_ROADMAP §3.3 Gap 3).

The retrieval flow we want is:

```
vector(top_n) ─┐
bm25(top_n)   ─┼─ RRF(k=60) ─→ top_30 ─→ Rerank ─→ top_K (default K=8)
graph(top_n)  ─┘
```

with `library_id` enforced at every adapter boundary.

A second pressure: ADR-0017's CRAG evaluator wants a cross-encoder to score
`(query, chunk)` pairs and bucket them by confidence. If we pick a different
model for CRAG vs rerank, the worker box loads two cross-encoders; if we pick
the same model and share the forward pass, we pay once. ADR-0017 §3 commits
to the joint-scoring contract and **this ADR commits to making it possible**.

### Forces

- **Latency budget.** PRD §3.2 lists P95 query latency as a leading guardrail;
  rerank cannot blow past 200 ms on top-30 candidates or the QA stream stalls.
- **Cost discipline.** Rerank-as-a-service (Cohere, Jina) bills per 1k
  candidates. At 30 candidates × 100 queries/day × 50 Libraries the meter
  spins fast; ADR-0015 daily caps make this user-visible.
- **GPU footprint.** The worker box already runs BGE-M3 embedder. Adding a
  second 568M-parameter cross-encoder is feasible; adding two is not.
- **Library-agnostic computation.** Rerank scores `(query, text)` pairs; it
  has no Library-scoped state. But the **input candidates** are
  Library-scoped, so the function signature still takes `library_id` to keep
  the §16.6 discipline and to allow per-Library model overrides
  (ADR-0012 / `LibraryConfig.embedder_override`).
- **Multilingual corpora.** PRD §17 R02 is the existing parser-fallback rule;
  reranker quality on Chinese / mixed CJK content with technical English
  terms is uneven across vendors.
- **Reuse with CRAG.** ADR-0017 must reuse this model. Without sharing, GPU
  memory doubles and CRAG's "free" evaluation stops being free.

## Decision

We adopt **BGE-reranker-v2 (BAAI/bge-reranker-v2-m3) deployed locally** as
the primary reranker, with **Cohere Rerank v3 as a swappable fallback** when
the local model is unavailable or returns degenerate scores. RRF runs first
(deterministic, free) over the three-route candidates; the reranker only
sees the top-30 fused list.

### 1. `Reranker` Protocol contract

The Protocol lives in `packages/indexing/reranker.py` (per BACKEND_ROADMAP
§3.3 Gap 3). It takes `library_id` as the first non-self argument so per-
Library overrides are possible (ADR-0012), even though the underlying
computation is Library-agnostic.

```python
# packages/indexing/reranker.py
from typing import Protocol

from packages.core.models import RetrievedEvidence


class Reranker(Protocol):
    name: str  # "bge-reranker-v2-m3" | "cohere-rerank-v3" | "noop"

    async def rerank(
        self,
        library_id: str,
        query: str,
        candidates: list[RetrievedEvidence],
        *,
        top_k: int = 8,
    ) -> list[RetrievedEvidence]: ...

    async def score(
        self,
        library_id: str,
        query: str,
        texts: list[str],
    ) -> list[float]: ...
```

`rerank` returns sorted, truncated evidence with `rank_after_rerank` filled
in (PRD §9.4 model field). `score` exposes the raw cross-encoder scores so
ADR-0017's CRAG evaluator can call **one** forward pass and use the result
both for ranking and for confidence bucketing.

### 2. Pipeline order: RRF → Rerank

```python
# packages/indexing/coordinator.py — pseudocode for HybridRetrievalCoordinator.search
async def search(self, library_id, query, k=8) -> list[RetrievedEvidence]:
    runs = await asyncio.gather(
        self._vector.search(library_id, query, k=30),
        self._bm25.search(library_id, query, k=30),
        self._graph.expand(library_id, query, k=30),
    )
    fused = reciprocal_rank_fusion(runs, k=60, top_n=30)   # packages/indexing/fusion.py
    if len(fused) < SKIP_RERANK_THRESHOLD:                 # 5
        return fused[:k]
    try:
        return await self._reranker.rerank(library_id, query.text, fused, top_k=k)
    except RerankerTimeout:
        return fused[:k]                                   # graceful degrade
```

- **RRF first** because it is deterministic, free, and harmonizes scores
  across heterogeneous routes (cosine score / BM25 / graph relevance live on
  different scales). Constant `k=60` matches Cormack et al. (2009).
- **Rerank second** on `top_30`. Beyond 30 the latency cost is not justified
  by ranking quality on the M2 multihop eval set.
- **Skip rerank when candidate count < 5.** With four or fewer candidates,
  RRF has already placed them; cross-encoder scoring adds latency without
  changing order in 90%+ of cases on our smoke set.

### 3. Latency contract

| Hardware                     | top-30 latency target | Hard timeout |
|------------------------------|-----------------------|--------------|
| Local: BGE-reranker-v2-m3 on CUDA (RTX 3090 / A10) | P95 ≤ 120 ms | 200 ms |
| Local: BGE-reranker-v2-m3 on CPU (fallback)        | P95 ≤ 600 ms | 1000 ms |
| Cohere Rerank v3 (cloud)                           | P95 ≤ 250 ms | 500 ms |

Timeouts trigger the graceful-degrade path (return RRF top-K). The timeout is
logged as `reranker.timeout` to Langfuse with `library_id` and query length
so we can see which Libraries are getting starved.

### 4. Fallback chain (per PRD §17 R02 pattern)

`Reranker` is composed by a `FallbackReranker` that walks an ordered chain.
Each entry has its own timeout and error class.

```python
# packages/indexing/fallback_reranker.py
class FallbackReranker:
    def __init__(self, chain: list[Reranker]):
        self._chain = chain  # e.g. [LocalBGE(), CohereRerank(), NoopReranker()]

    async def rerank(self, library_id, query, candidates, top_k=8):
        for r in self._chain:
            try:
                return await asyncio.wait_for(
                    r.rerank(library_id, query, candidates, top_k=top_k),
                    timeout=TIMEOUTS[r.name],
                )
            except (RerankerTimeout, RerankerHealthError):
                logger.warning("reranker.fallback", from_=r.name)
                continue
        # final NoopReranker just returns candidates[:top_k]
```

The default chain is `[BGE, Cohere, Noop]`. Per-Library config
(ADR-0012, `LibraryConfig.reranker_chain_override`) can swap Cohere out for
Jina or pin the local model only — but the **noop tail is mandatory** so the
QA pipe never errors out for lack of a reranker.

### 5. Joint scoring with CRAG (ADR-0017)

The cross-encoder produces a vector of scores `[s_1 ... s_30]` for the top-30
candidates. We expose this vector once and reuse it twice:

- **Rank** by sorting on `s_i` and truncating to `top_k`.
- **Bucket** the same `s_i` for CRAG: `top_1 ≥ 0.70 → confident`, `top_1 <
  0.30 → incorrect`, otherwise `ambiguous` (ADR-0017 §3).

`HybridRetrievalCoordinator` exposes a one-shot
`search_with_scores(library_id, query, k)` that returns
`(ranked: list[RetrievedEvidence], scores: list[float])` so ADR-0017's CRAG
strategy does not pay for a second forward pass.

### 6. Skip / disable conditions

The reranker is **skipped** (RRF top-K returned directly) when:

- Candidate count < 5 (constant `SKIP_RERANK_THRESHOLD`).
- The query is a global / community-routing question (ADR-0006). Community
  summaries are not chunks; cross-encoder scoring on summaries is meaningless.
- The active `RetrievalBudget` already has < 50 ms of latency headroom
  (computed from `budget.timeout_s` minus elapsed time at the call site).
- `LibraryConfig.disable_reranker` is set (operator escape hatch for debug).

### 7. GPU sharing with embedder

Both BGE-M3 embedder and BGE-reranker-v2-m3 share the same backbone family
and tokenizer. They **do not** share weights, but they can share a single
worker process if we serialize calls. We therefore:

- Run the reranker in the **API process when CPU**, in the **worker process
  when GPU** — same as embedder. No new process.
- Cap concurrent rerank calls by an `asyncio.Semaphore(2)` per worker so
  embed jobs don't starve QA.
- Emit a `reranker.queue_wait_ms` metric so we know when contention is real.

### 8. Per-Library override

```python
# excerpt of LibraryConfig (ADR-0012 territory; this is the field added for ADR-0018)
class RerankerSpec(BaseModel):
    primary: str             # "bge-reranker-v2-m3" | "cohere-rerank-v3" | "noop"
    fallback: list[str]      # ordered fallback chain
    top_k: int = 8
    disable: bool = False    # debug only

class LibraryConfig(BaseModel):
    library_id: str
    reranker_override: RerankerSpec | None = None
    # ... other fields per ADR-0012
```

Default: not overridden → `[BGE, Cohere, Noop]` from global Settings.

## Consequences

### Positive

- **Citation F1 closes the M2 gap.** Internal benchmark on the 30-question
  multihop set: RRF-only Citation F1 ≈ 0.78; RRF + BGE-rerank ≈ 0.86. The
  M2 gate (≥ 0.80) and the M4 gate (≥ 0.85) both become reachable.
- **CRAG comes free.** ADR-0017's evaluator reuses the reranker forward pass.
  CRAG's incremental GPU cost is zero; its incremental latency is zero on
  the rerank path and ~120 ms on the no-rerank path.
- **Graceful degrade.** Local model down → Cohere → Noop. QA never blocks
  on a reranker outage.
- **Per-Library control.** A Library can pin Cohere (e.g. when the operator
  doesn't trust local scoring on Chinese-heavy corpora) without editing
  global config.

### Negative

- **GPU memory.** BGE-reranker-v2-m3 adds ~1.2 GB on top of BGE-M3 (~2.3 GB).
  Total GPU memory budget on the worker now ~4 GB before any LLM. Documented
  in OPERATOR_RUNBOOK.
- **Cohere fallback is a network dependency.** When local is degraded and
  Cohere has a regional outage, the chain falls all the way to Noop; rank
  quality regresses to RRF for the duration. Acceptable; user-visible only
  via slightly worse Citation F1 in that window.
- **Threshold constants.** `SKIP_RERANK_THRESHOLD=5`, RRF `k=60`, top-30
  cutoff — all are calibrated on a small smoke set. Recalibration needed
  when the corpus shifts language mix significantly.

### Risks

| Risk                                                | Mitigation                                                                      |
|-----------------------------------------------------|---------------------------------------------------------------------------------|
| BGE-reranker on mixed CJK / English under-scores    | Fallback chain pattern; per-Library override to pin Cohere; calibration set per Library |
| GPU OOM when reranker + embedder + LLM share box    | Semaphore(2) on rerank; embedder is already serialized; LLM runs through gateway with its own concurrency cap |
| Cohere API quota exhaustion                         | Daily cost cap (ADR-0015) catches it; chain falls to Noop; warning notification (ADR-0011) |
| Stale reranker model weights vs paper SOTA          | Model name pinned in `Settings`; upgrade tracked as ADR amendment, not silent  |
| Reranker cache poisoning via prompt injection       | Score cache key is `sha256(query + chunk_id)`; chunks themselves are operator-uploaded; no user-controlled cache writes |

## Alternatives Considered

| Option                                  | Rejected Because                                                                                              |
|-----------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **No rerank, RRF only**                 | Misses M2 Citation F1 gate by ~2 pp on multihop set; long-tail queries with shared lexical surface fail       |
| **Cohere Rerank as primary (cloud-first)** | Per-call cost; ADR-0015 daily caps would trip on heavy days; outbound dependency on a third party for hot path |
| **Jina Reranker as primary**            | Comparable quality on English; weaker on Chinese in our smoke; less battle-tested in the OSS community        |
| **Custom listwise reranker (mono/T5-mini)** | Training data we don't have; iteration cost weeks; ADR-0017's no-LLM-training mandate transitively applies   |
| **Two cross-encoders (one for CRAG, one for rerank)** | Doubles GPU memory; defeats ADR-0017 §3 reuse decision; no measurable quality lift for the cost              |
| **Rerank on top-100 instead of top-30** | 3× latency at marginal quality gain; smoke-set nDCG@10 plateaus past top-30                                   |

## Open Questions

1. **Should we calibrate `SKIP_RERANK_THRESHOLD` per Library?** Some
   Libraries with very tight ontologies always return < 5 candidates;
   skipping is fine. Some return 30 every time; skipping is moot. The
   constant works today; reopen if a real Library hits the boundary often.
2. **MTEB-Chinese refresh.** Re-bench BGE-reranker against newer Chinese
   reranker checkpoints (Tao 8B, Qwen3-reranker) every 6 months. Tracked
   as an ops cadence item, not a blocker for this ADR.
3. **Should the Noop tail rerank by RRF score, or pass through unchanged?**
   Today: pass through (already RRF-sorted). If future fusion changes
   semantics, revisit.
4. **Per-conversation reranker pinning.** ADR-0017 caches strategy decisions
   per conversation. Should the reranker also be pinned per conversation for
   consistency? Provisional: no, the reranker is library-level state.

## Relationships With Other ADRs

- **ADR-0001 (Modular Monolith)** — `Reranker` Protocol lives in
  `packages/indexing/`. Coordinator depends on it; strategies depend on
  coordinator. No cross-package shortcut.
- **ADR-0003 (Library as Data Partition)** — `library_id` is the first
  argument even though scoring is Library-agnostic. This keeps the
  contract uniform with §16.6 and enables per-Library overrides.
- **ADR-0007 (Error Envelope)** — `RerankerTimeout` and
  `RerankerHealthError` map to `RKBError` codes
  `RERANKER_TIMEOUT` / `RERANKER_UNAVAILABLE`. The graceful-degrade path
  swallows these; the surface error is only emitted when **all** entries
  in the chain fail.
- **ADR-0012 (per-Library Config)** — `RerankerSpec` is one of the
  override fields. Without ADR-0012's config store, the Library-level
  pinning in §8 has nowhere to live; this ADR therefore declares a
  soft dependency on ADR-0012 landing first.
- **ADR-0015 (Daily Cost Cap)** — Cohere fallback usage charges to the
  per-Library daily cost; warn at 80%, block at 100% as for LLM calls.
- **ADR-0017 (Self-RAG / CRAG / ToG)** — CRAG reuses the reranker score
  vector. The `score()` method on the Protocol exists specifically for
  ADR-0017 §3.

## References

- PRD §9.2 (M2 Scope: RerankerService line), §9.4 (`RetrievedEvidence`
  with `rank_after_rerank`), §9.6 (Citation F1 ≥ 0.80 gate)
- PRD §17 R02 (parser fallback chain — same pattern applied here)
- BACKEND_ROADMAP §3.3 Gap 3 (file plan: `fusion.py`, `reranker.py`),
  §5 (ADR-0018 line item)
- Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet and
  individual Rank Learning Methods," SIGIR 2009 — RRF k=60 origin
- Xiao et al., "C-Pack: Packaged Resources To Advance General Chinese
  Embedding," 2023 — BGE family
- BAAI/bge-reranker-v2-m3 model card (HuggingFace)
- `packages/indexing/coordinator.py` — current implementation that this
  ADR mutates
- `packages/embedding/service.py` — sibling pattern (local primary +
  cloud fallback) the reranker chain mirrors
