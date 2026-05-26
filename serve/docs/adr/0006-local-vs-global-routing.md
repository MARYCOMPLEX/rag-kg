# ADR 0006: Local vs. Global Routing — Heuristic Classifier in M3, LLM Classifier in M4

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

After M3 lands, the system has **two retrieval modes** within a single Library:

- **Local search** — the M2 hybrid pipeline (vector + graph + BM25 → RRF → rerank). Returns chunk-level evidence. Best for specific factual questions ("Which dataset did paper X use?").
- **Global search** — query the per-Library `communities_<library_id>` collection produced by ADR 0004 + ADR 0005. Returns community-level summaries. Best for synoptic questions ("What are the main approaches in this subfield?").

Every incoming question must be routed to one mode (or, in the future, both). The router runs **once per query** on the hot path, before any retrieval — so its latency and cost contribute directly to the user-visible response time (`PRD §3.2` budgets P95 ≤ 20s end-to-end for QA).

Two natural designs:

| Approach | Cost per query | Latency added | Accuracy ceiling |
|---|---|---|---|
| **Heuristic** (word lists + length + entity hits) | $0 | <5 ms | Capped — misses paraphrases and ambiguous questions |
| **LLM classifier** (single short call, e.g. Haiku with 1-shot prompt) | ~$0.0001–$0.0005 | ~300–800 ms | High — generalizes well to phrasing variants |

The PRD's M3 exit criterion (`PRD §10.4`, D3.4) is "10 道分类题准确率 ≥ 0.85" — a modest bar a heuristic can plausibly hit on a small evaluation set.

The key design question: **Should M3 ship a heuristic router (cheap, predictable, capped quality) or an LLM-based router (more accurate, adds per-query cost + latency)?**

## Decision

**M3 ships a heuristic router. M4 will replace it with an LLM classifier as part of the reflection-planner work, with the heuristic kept as a fallback.**

Concretely:

1. **Implementation**: `packages/orchestration/routing/heuristic_router.py` exposes:

```python
class QueryRoute(BaseModel):
    library_id: str
    mode: Literal["local", "global", "hybrid"]
    confidence: float   # 0.0-1.0
    rationale: str      # human-readable, for trace + debug

class QueryRouter(Protocol):
    async def route(
        self, library_id: str, query: Query
    ) -> QueryRoute: ...
```

2. **No LLM call.** The router is pure Python — feature extraction + scoring rules.

3. **Signals used** (combined into a weighted score):
   - **Trigger word hits** in EN + ZH (see lists below).
   - **Query length in tokens** (very short queries skew local; long open-ended queries skew global).
   - **Specific-entity hit count** — does the query mention any entity present in this Library's KG? The check is a fast Redis lookup against `entity_aliases_<library_id>`. Many entity hits → local; zero entity hits + long question → global.
   - **Question shape** — interrogatives like "what / which / when / 在哪 / 是什么" tilt local; "summarize / overview / landscape / 综述 / 总结 / 主流" tilt global.

4. **Trigger word lists** (kept in `packages/orchestration/routing/triggers.py`, versioned for testability):

   - **Global-leaning (EN)**: `summary, summarize, summarise, overview, landscape, mainstream, common themes, broadly, in general, survey, review, themes, trends, taxonomy, categories`.
   - **Global-leaning (ZH)**: `综述, 总结, 概览, 总体, 整体, 大体, 趋势, 主流, 全貌, 汇总, 分类, 类别, 体系`.
   - **Local-leaning (EN)**: `which, when, who, where, exact, specifically, dataset, score, accuracy, formula, equation, in paper, in section`.
   - **Local-leaning (ZH)**: `哪个, 何时, 在哪, 在哪里, 谁, 具体, 数据集, 公式, 论文, 章节, 第几`.

5. **Scoring**: each signal contributes a signed score; final mode is `global` if score > positive threshold, `local` if score < negative threshold, `hybrid` in between. Thresholds live in `Settings.routing` so they can be tuned per-Library if needed.

6. **`hybrid` mode** runs both local and global retrieval and merges with RRF before rerank. It exists as a safe middle for ambiguous queries — better to spend a bit more retrieval budget than to misroute. Hybrid is the default fallback when confidence is low.

7. **Instrumentation for the M4 swap**:
   - Every `QueryRoute` is written to the `RetrievalTrace` (already includes `library_id` per ADR 0003) with mode, confidence, rationale, and the input query.
   - This produces an organic dataset of (query, heuristic decision, downstream answer quality) tuples that M4 can use to train/evaluate the LLM-classifier replacement and to A/B against the heuristic.

8. **Per-Library** — like every other operation, routing takes `library_id` first and consults that Library's entity index. The entity-hit signal makes the router naturally Library-aware: rare-term queries score higher in the Library that knows the term.

## Consequences

### Positive

- **Zero per-query cost and near-zero latency.** Heuristic evaluation is microseconds, well under the network round-trip to any LLM.
- **Predictable + debuggable.** A reviewer can read the trigger word list and predict the route. When the router misroutes, the rationale string explains why.
- **No new external dependency on the hot path.** No extra LLM-Gateway hop, no extra failure mode, no extra timeout to tune.
- **Generates training data for free.** The per-query trace is exactly the dataset M4's LLM-classifier needs, so the heuristic isn't throwaway work — it's an instrumentation layer.
- **`hybrid` as the safe default for low-confidence queries** keeps quality from collapsing on ambiguous inputs.

### Negative

- **Quality ceiling.** The heuristic will misroute paraphrases ("give me the lay of the land in this area" has zero trigger-list overlap but is clearly global). We expect failure cases concentrated in: poetic phrasings, code-mixed EN/ZH queries, and queries that ask for a list of specific items but in a survey-like tone.
- **Trigger word lists drift over time.** Adding new keywords requires a code change + redeploy. Mitigation: lists are isolated in one tiny file; PRs touching them are tiny.
- **No cross-language transfer.** Adding a third language means handcrafting another list rather than relying on multilingual LLM understanding.

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Routing accuracy < 85% on the M3 D3.4 set | Medium | Iterate trigger lists during M3 development; if still under 85% after one tuning pass, escalate the M4 LLM-classifier work. |
| Users learn to "game" the keywords ("write summary of paper X" gets misrouted to global) | Low | The entity-hit signal counterbalances: a query mentioning a specific paper title scores local even if the verb is "summarize". |
| Hybrid mode becomes the default for too many queries → wasted retrieval budget | Medium | Track hybrid-rate in the M6 dashboard; tune thresholds if it exceeds a comfortable share of traffic. |
| The heuristic routes a "global" question to local but local happens to find a passable answer, masking the error | Low | M6 evaluation specifically includes a routing-accuracy metric independent of answer-quality, so this kind of silent miss surfaces. |

### Failure Modes & Mitigation

| Failure mode | What user sees | Mitigation in M3 |
|---|---|---|
| Global question routed to local | A scattered, chunk-level answer that misses the synthesis | `hybrid` fallback for low-confidence queries; user can manually pass `--mode global` via CLI |
| Local question routed to global | A high-level summary that doesn't answer the specific question | Same: `hybrid` fallback; explicit override flag |
| Code-mixed EN/ZH query that hits both lists | Score cancels out → routed to `hybrid` | Acceptable — `hybrid` is the safe middle |
| Empty entity index for a fresh Library | Entity-hit signal is 0; router relies on word lists + length only | Documented behavior; first ingestion run populates the entity index |

### Why Not Skip Straight to the LLM Classifier?

We considered shipping the LLM classifier directly in M3 and skipping the heuristic. Three reasons not to:

1. **No reflection planner exists yet.** M4 introduces the LLM-driven planning layer (`PRD §11`) where this classifier naturally fits. Building it in M3 means writing throwaway plumbing that M4 will rework.
2. **No evaluation data.** We have no labeled "global vs local" set yet. Shipping an LLM classifier without an evaluation set means we have no way to know if it actually beats a heuristic.
3. **Latency budget pressure.** Adding 300–800 ms per query in M3 — before we've even profiled the rest of the pipeline — eats into the P95 ≤ 20s budget without justification.

The heuristic is therefore the **instrumented baseline**: it ships traffic, generates labeled data, and gets replaced when the M4 work has a measurable lift to point at.

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| **LLM classifier from day one (M3)** | Adds per-query cost + 300–800 ms latency without an evaluation set to justify the lift. Belongs in M4 with the rest of the reflection-planner work. |
| **Always run hybrid (no router at all)** | Doubles retrieval cost on every query. Defensible if hybrid quality dominated, but our M2 work showed local hybrid is strictly worse than community-summary on synoptic questions and vice versa — so always-hybrid wastes budget on the wrong half. |
| **Embedding-based classifier** (cosine-sim against centroids of "global" and "local" example queries) | More principled than word lists, but introduces an embedding call per query (still adds latency) and requires labeled examples we don't have yet. |
| **User-mode toggle (force user to pick local vs global in UI)** | Pushes a system concept onto the user — exactly the kind of cognitive load `PRD §14` (UX hardening) wants to avoid. Reasonable as a power-user override but bad as the default. |
| **Rule-based grammar parser** (full PoS tagging, parse tree) | Heavyweight setup, marginal accuracy gain over keyword + length on questions of this length. spaCy or stanza models add several hundred MB to the deploy. |
| **Train a small classifier (logistic regression on bag-of-words)** | Needs training data we don't have. The heuristic is the bootstrapping step that produces that data; once we have it (post-M3), fine-tuning a small model becomes a real option for an M4-or-later upgrade. |

## References

- Edge et al. *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv 2404.16130 (2024). [`data/libraries/rag-agent/corpus/spike/2404.16130.pdf`] — defines the local/global split this router decides between.
- Gutiérrez et al. *HippoRAG.* arXiv 2405.14831 (2024). [`data/libraries/rag-agent/corpus/spike/2405.14831.pdf`] — uses entity-anchored signals at retrieval time; informed the entity-hit feature.
- Guo et al. *LightRAG.* arXiv 2501.14998 (2025). [`data/libraries/rag-agent/corpus/spike/2501.14998.pdf`] — argues that lightweight routing decisions can match heavier ones at small/medium scale.
- Cross-references: ADR 0003 (router takes `library_id` first; entity-hit signal queries the per-Library index); ADR 0004 (global mode targets the community hierarchy this ADR's output indexes); ADR 0005 (global mode retrieves the JSON summaries this ADR's output indexes); future M4 ADR will document the LLM-classifier replacement and the A/B methodology.
