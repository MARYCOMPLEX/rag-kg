# ADR 0005: Community Summary Prompt Design — Single-Call JSON, Capped Inputs

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

M3 (`PRD §10`) requires that every community produced by ADR 0004 be turned into a **short natural-language summary** suitable for vector retrieval during global search. The summary is the unit indexed in the `communities_<library_id>` Qdrant collection; its quality directly determines whether "整体性" questions (`PRD §2.2 UC3`) hit the right community.

The GraphRAG paper (2404.16130) uses an LLM to summarize each community by passing it the entities + their relationships. HippoRAG (2405.14831) and LightRAG (2501.14998) take similar but lighter-weight approaches. None of them publish a prompt that fits our constraints, so we have to make our own design choices.

The core tradeoffs:

1. **Cost.** A typical Library at M3 contains O(50) communities at level-0 and O(10) at level-1. With even a modest model (Claude Haiku class) at roughly $0.0002–$0.001 per summary, the per-rebuild bill is real money over time, especially with daily incremental rebuilds (`PRD §10.2`).
2. **Quality.** The summary must be specific enough to discriminate between communities ("Transformer architectures for long-context QA" vs. "Retrieval-augmented summarization"), not so generic it collapses into "this community is about NLP."
3. **Determinism.** `PRD §10.5` lists summary churn as a risk. We need cacheability so unchanged communities keep their summary across rebuilds.
4. **Structure.** The UI (M7, `PRD §14`) needs a `title` for tab labels and a list of `representative_entities` for the KG browser. Free-text summaries make this awkward to extract.
5. **Prompt size.** Naively passing every entity name + every triple in a community blows up the prompt for large communities (some can have 100+ entities and 500+ triples), wasting tokens on tail noise.

The key design question: **What is the minimal prompt design that gives us structured, cacheable, bounded-cost summaries that are useful for both vector retrieval and the UI?**

## Decision

**One LLM call per community returning a small JSON object, with hard caps on input size.**

Concretely:

1. **One call per community.** No multi-pass refinement. No per-relation summaries. No two-stage extract-then-write.
2. **Output is JSON** with three fields:

```python
class CommunitySummary(BaseModel):
    library_id: str
    community_id: str
    title: str                          # 8-15 words, noun phrase
    summary: str                        # 2-3 sentences, 80-200 words
    representative_entities: list[str]  # 3-5 entity_ids, ranked by centrality
```

3. **Inputs are capped** before they hit the prompt:
   - **Max 30 entities** per community, ranked by **degree centrality within the community subgraph**. Tie-broken by entity name length (shorter first — proxy for canonical names over messy aliases).
   - **Max 80 triples** per community, ranked by **edge weight** (co-occurrence count in source chunks). For each kept triple we pass `head.name`, `relation`, `tail.name` — no `evidence` chunk text.
   - These caps are constants in `packages/indexing/community/prompts.py`: `MAX_ENTITIES_IN_PROMPT = 30`, `MAX_TRIPLES_IN_PROMPT = 80`.
4. **Temperature is `0.0`.** Combined with a fixed system prompt and ranked inputs, the same community → same prompt → same output. This makes Redis-keyed caching trivial: cache key = `sha256(library_id, community_id, prompt_template_version, sorted_entity_ids, sorted_triple_ids)`.
5. **Model selection** goes through the existing LLM Gateway with `prefer_local=True` (defined in `PRD §8.2`). For M3 we default to a small/fast model (Haiku class or local Qwen2.5-7B); the Gateway handles fallback if the local model is unhealthy.
6. **Single-pass retry.** If the response fails JSON parsing, retry exactly once with a stricter "respond ONLY with JSON" reminder. After two failures we mark the community `summary_status = "failed"` and skip it; the rebuild does not crash.
7. **The summary text indexed in Qdrant** is `f"{title}\n\n{summary}"` — concatenating both fields gives the embedder both the dense topical signal and the discriminative detail.

### Prompt sketch (truncated for brevity)

```text
SYSTEM: You are summarizing a knowledge-graph community for a research
assistant. Output ONLY valid JSON matching the given schema. No prose
outside the JSON.

USER:
Community ID: <id>
Top entities (ranked by centrality):
- <entity_name_1> (<type>): <description?>
- ...
Key relationships:
- <head> -- <relation> --> <tail>
- ...

Produce a JSON object with fields: title, summary, representative_entities.
- title: 8-15 word noun phrase capturing the topic
- summary: 2-3 sentences (80-200 words), specific not generic
- representative_entities: 3-5 entity names from the list above
```

The full template lives in `packages/indexing/community/prompts.py` and is versioned (`PROMPT_TEMPLATE_VERSION = "v1"`) so prompt edits invalidate the cache automatically.

### Cost estimate

For a Library with ~50 communities (level-0 + level-1 combined), at an estimated ~600 input tokens + ~150 output tokens per summary, against a Haiku-tier model priced near $0.0002 per call, a **full rebuild is estimated at ~$0.01 per Library**. Incremental rebuilds (only changed communities) should be substantially cheaper. Numbers are estimates from public price sheets; actual values will be measured in M6 (`PRD §13`) and reported in the dashboard.

## Consequences

### Positive

- **Bounded cost.** Even a 500-entity community pays the same prompt price as a 30-entity one. Worst-case spend per rebuild is predictable from the community count alone.
- **Cacheable.** Temperature 0 + deterministic input ordering + content-hash key means a re-run on unchanged data costs $0 in LLM tokens — important for daily incremental rebuilds (`PRD §10.2`).
- **Structured output drives UI directly.** `title` lights up the community tab, `representative_entities` becomes the chip row, `summary` is the body. No parsing of free-form text.
- **Pluggable model.** Going through the LLM Gateway means we can switch from Haiku-class to a local Qwen model without touching this code.
- **Easy to audit.** Each summary record stores the prompt template version + the input-content hash, so a reviewer can trace exactly what produced it.

### Negative

- **Capping loses long-tail context.** Communities with rich structure beyond top-30 entities silently drop the rest. We expect this is fine because the dropped entities are by definition lower-centrality, but in pathological "one giant component" Libraries it could hurt. Mitigation: log when caps were hit and surface in M6 dashboards.
- **Single-pass means no self-correction.** A bad first draft is the final draft. Mitigation: M4's critic loop (`PRD §11`) can later re-evaluate summaries during global search; if quality is bad we add a refinement pass then.
- **JSON-mode reliability varies by model.** Some self-hosted models drift out of strict JSON. Mitigation: response-format hint where supported; one retry; explicit failure marker rather than crash.

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Daily rebuild cost balloons as Libraries grow | Medium | Incremental strategy (only changed communities) is mandatory by `PRD §10.4`. Cache hits for unchanged communities should dominate steady-state cost. |
| Prompt template change silently invalidates all summaries | Low | `PROMPT_TEMPLATE_VERSION` is part of the cache key. Bumping the version is the explicit "rebuild everything" signal. |
| Summary too generic to discriminate communities | Medium | M6 evaluation: measure community retrieval precision against a labeled set; if precision is low, revisit prompt or move to multi-pass refinement. |
| Cross-Library leakage in summary (entity from wrong Library) | Low | All entity inputs are filtered by `library_id` upstream; ADR 0003's per-Library partitioning makes this structurally impossible. Defensive assertion in writer. |

### Why Not Multi-Pass Refinement?

GraphRAG itself uses a more elaborate map-reduce summarization for very large communities. We considered it and rejected for M3:

- Our per-Library scale (a few thousand entities total) means most communities fit comfortably under the cap.
- Multi-pass roughly **doubles or triples** the per-rebuild cost.
- The M3 risk register (`PRD §10.5`) explicitly flags LLM cost as a top concern.

If M6 evaluation shows the single-pass approach is the bottleneck on global-QA quality, refinement becomes a clear M3.x candidate.

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| **Free-form text summary (no JSON)** | Forces brittle regex extraction for `title` and `representative_entities`. JSON output is now reliably supported by Haiku-class models and most local models with grammar constraints. |
| **Per-relation summaries** ("for each relation type, summarize…") | Multiplies LLM calls per community by the number of relation types (often 5–10). Cost grows multiplicatively without clear quality gain at our scale. |
| **Two-pass: extract then write** | Two LLM calls per community doubles cost. The extraction step is essentially what we already did during M2 KG construction; doing it again is waste. |
| **Multi-pass refinement (GraphRAG-style map-reduce)** | Best quality but ~3× cost. Not justified at M3 scale; revisit if M6 evaluation shows summary quality is the bottleneck. |
| **No LLM — use entity-name centroid embedding as the "summary"** | Cheapest possible, but produces summaries that cannot be shown to users in the UI. Loses the dual-purpose benefit (retrieval + display). |
| **Chunk-text concatenation summary (no LLM, just paste evidence chunks)** | Bypasses LLM entirely but produces multi-thousand-token "summaries" that defeat the purpose of community-level retrieval (which is meant to be coarser-grained than chunks). |
| **Streaming structured output without temperature 0** | Loses cacheability. The whole determinism story collapses if the same input gives different outputs across rebuilds. |
| **Higher caps (e.g., 100 entities / 300 triples)** | Linear cost increase with no evidence of quality lift. Caps can be raised later in `Settings`; rejecting the higher default is the conservative starting point. |

## References

- Edge et al. *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv 2404.16130 (2024). [`data/libraries/rag-agent/corpus/spike/2404.16130.pdf`] — original community-summary recipe; we adopt the structure but simplify to single-pass.
- Gutiérrez et al. *HippoRAG.* arXiv 2405.14831 (2024). [`data/libraries/rag-agent/corpus/spike/2405.14831.pdf`] — alternative entity-anchored summarization; informed our `representative_entities` field.
- Guo et al. *LightRAG.* arXiv 2501.14998 (2025). [`data/libraries/rag-agent/corpus/spike/2501.14998.pdf`] — confirms that lightweight summarization is competitive with heavy multi-pass approaches at small/medium scale.
- Cross-references: ADR 0003 (every summary carries `library_id`; entity inputs are pre-filtered per-Library); ADR 0004 (the `CommunityDetector` output is the input to this prompt); ADR 0006 (the global-search router decides when to retrieve from these summaries vs. raw chunks).
