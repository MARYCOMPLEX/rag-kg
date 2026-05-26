# ADR 0004: Community Detection — python-louvain for M3 Baseline (Leiden Deferred)

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

M3 (`PRD §10`) introduces **Community Detection + Global Search** on top of the per-Library knowledge graph built in M2. The goal is to answer "整体性 / 综合性" questions (e.g. "What are the mainstream methods in this subfield?") by retrieving **community-level summaries** instead of individual chunks — the GraphRAG (Microsoft, 2404.16130) recipe.

This requires a graph clustering algorithm that:

1. Runs on per-Library KGs of **a few thousand nodes** (typical M3 size after ~200 papers ingested).
2. Is **deterministic given a seed**, so summaries don't churn between rebuilds with identical inputs.
3. Supports **hierarchical clustering** (level-0 fine-grained → level-1 coarse) so global queries can pick the right granularity.
4. Has a **simple install path** (Python wheel, no opaque C build steps) — important for the modular-monolith era.
5. Is **fast enough** that an incremental community rebuild does not block ingestion (`PRD §10.4` requires it runs on a separate worker).

Two industry-standard choices dominate the modularity-based clustering literature:

| Library | Algorithm | Install | License |
|---|---|---|---|
| `python-louvain` (a.k.a. `community`) | Louvain (Blondel et al., 2008) | Pure Python wheel | BSD-3 |
| `leidenalg` + `python-igraph` | Leiden (Traag et al., 2019) | Requires `igraph` C extension (compiled) | GPL-3 (igraph) / GPL-3 (leidenalg) |

The original GraphRAG paper uses **Leiden**. The HippoRAG (2405.14831) and LightRAG (2501.14998) papers do not strictly require Leiden either — they treat the partitioner as a swappable component.

The key design question: **Should M3 ship Leiden (best quality, heavier install) or Louvain (good quality, lightest dependency)?**

## Decision

**M3 uses `python-louvain` for level-0 + level-1 community detection. Leiden remains a candidate for an M3.x quality upgrade once we have evaluation data justifying the install cost.**

Concretely:

1. **Adapter**: `packages/indexing/community/louvain_detector.py` implements the `CommunityDetector` Protocol.
2. **Per-Library**: every detection run takes `library_id` as its first argument and operates on the KG of that Library only — no cross-Library partitioning.
3. **Seed**: detection is called with a fixed `random_state` from `Settings.community.seed`. Re-running on identical input must produce identical partitions (guarded by a unit test).
4. **Hierarchy** (max 2 levels for M3):
   - **Level-0** — run Louvain directly on the KG (entities as nodes, triples as weighted edges; weight = co-occurrence count).
   - **Level-1** — aggregate level-0 communities into a meta-graph (one node per level-0 community, edge weight = sum of inter-community triple counts), then run Louvain again.
   - Stop after level-1. Three levels would add cost without measurable gain at our scale.
5. **No connectivity post-processing** in M3. We accept the rare non-connected-community case (see Negative below) and only log a warning.
6. **Protocol shape** is identical to what a Leiden adapter would expose, so swapping later is one-file work:

```python
class CommunityDetector(Protocol):
    async def detect(
        self,
        library_id: str,
        graph: KGSnapshot,
        *,
        seed: int,
        max_levels: int = 2,
    ) -> CommunityHierarchy: ...
```

7. **Storage**: detection output (`CommunityHierarchy`) is persisted in Postgres per Library; the dependency on a specific algorithm does not leak into downstream code (summarizer, indexer, retriever).

## Consequences

### Positive

- **Simplest possible install path.** `python-louvain` is a small pure-Python wheel — `uv sync` works on Mac/Linux/Windows without compilers, matching the "10-minute new-machine onboarding" target from M0 (`PRD §7.7`).
- **Deterministic given seed.** Combined with the M3 risk register entry on Leiden instability (`PRD §10.5`), seeding Louvain gives us the determinism we want with no extra effort.
- **Fast enough at our scale.** Louvain is O(n log n) in practice; we expect a few-thousand-node KG to partition in well under a minute on a single CPU core, leaving the 2-minute budget from `D3.1` (`PRD §10.3`) almost entirely to summarization.
- **Identical Protocol surface to a Leiden adapter.** When and if we swap, no caller changes.
- **License compatibility.** BSD-3 imposes no copyleft on the rest of the codebase. `igraph`/`leidenalg` are GPL-3, which would force us to think harder about how `packages/indexing` is distributed.

### Negative

- **Lower partition quality than Leiden in adversarial cases.** Louvain can occasionally produce **non-connected communities** — a node group labeled as one community even though removing the bridging edge would split it. Leiden's refinement step provably eliminates this. Mitigation: log + count occurrences during rebuild; if the rate climbs above a threshold we revisit (see Risks).
- **Modularity resolution limit.** Like all modularity maximizers, Louvain may merge small genuine communities under a single label at default resolution. We will expose `Settings.community.resolution` (default `1.0`) so it can be tuned per-Library if needed.
- **Greedy local moves** can yield slightly different partitions across `python-louvain` versions even with the same seed. Mitigation: pin the package version in `pyproject.toml`; re-evaluate on upgrade.

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Non-connected community shows up in a UI summary, looks broken | Medium | Detect at write time (`networkx.is_connected` per partition); on detection, split into connected sub-communities before summarizing. Cheap fix because it's post-hoc. |
| KG grows to tens of thousands of nodes per Library and Louvain becomes the slow path | Low (M3 scale) | Profile at M5 with the first real Library; promote Leiden if Louvain rebuild exceeds the 2-minute target on the same hardware. |
| Library rebuilds drift across `python-louvain` minor versions | Low | Pin exact version; document upgrade as an ADR-worthy decision. |

### Why Not Leiden Now?

The marginal quality gain from Leiden is **not worth a compiled C dependency at M3**. The system is still pre-evaluation: we have no community-quality benchmark yet. Adding `igraph`/`leidenalg` would:

- Force every contributor to install C build tools.
- Force CI images to ship the `igraph` shared library.
- Push us into GPL-3 territory for one package without first proving we need the quality.

The right time to switch is **after M6** (`PRD §13`) when we can A/B Louvain vs. Leiden against the gold global-QA set and measure the lift in dollars-per-quality-point.

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| **Leiden (`leidenalg` + `python-igraph`)** | Higher quality and provably connected partitions, but introduces a compiled C dependency (`igraph`), GPL-3 license, and heavier CI image. Deferred to M3.x when we have evaluation data justifying the cost. |
| **Girvan–Newman (edge-betweenness)** | O(VE²) — orders of magnitude slower than Louvain. Acceptable for graphs with hundreds of nodes, not thousands. |
| **Label Propagation (`networkx.algorithms.community.label_propagation`)** | Very fast, but **non-deterministic by design** (random tie-breaking) and produces lower-modularity partitions than Louvain on dense subgraphs. Determinism is an M3 requirement. |
| **Infomap (`infomap` Python binding)** | Strong on flow-based community structure, but introduces another C extension and we have no evidence its information-theoretic objective matches "useful summary granularity" better than modularity. |
| **Spectral clustering (`scikit-learn`)** | Requires choosing `k` upfront; M3 wants the algorithm to choose granularity. Adds a hyperparameter we don't know how to tune per-Library. |
| **No clustering — summarize every entity neighborhood** | Doesn't scale: an N-entity Library would need N summaries, blowing the LLM budget (see ADR 0005). Defeats the purpose of GraphRAG-style global retrieval. |
| **Hierarchical agglomerative on entity embeddings (no graph structure)** | Ignores the KG structure that M2 spent three weeks building. Modularity-based methods exploit precisely this signal. |

## References

- Blondel, Guillaume, Lambiotte, Lefebvre. *Fast unfolding of communities in large networks.* J. Stat. Mech. 2008. (Louvain)
- Traag, Waltman, van Eck. *From Louvain to Leiden: guaranteeing well-connected communities.* Sci. Rep. 2019.
- Edge et al. *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv 2404.16130 (2024). [`data/libraries/rag-agent/corpus/spike/2404.16130.pdf`]
- Gutiérrez et al. *HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs.* arXiv 2405.14831 (2024). [`data/libraries/rag-agent/corpus/spike/2405.14831.pdf`]
- Guo et al. *LightRAG: Simple and Fast Retrieval-Augmented Generation.* arXiv 2501.14998 (2025). [`data/libraries/rag-agent/corpus/spike/2501.14998.pdf`]
- Cross-references: ADR 0003 (Library partitioning — every detection run is per-`library_id`); ADR 0005 (community summary prompt design — consumes this ADR's output); ADR 0006 (local-vs-global routing — chooses when to query the community index).
