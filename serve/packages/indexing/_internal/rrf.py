"""Reciprocal Rank Fusion over heterogeneous retrieval runs.

ADR-0018 §2 pipeline: vector + bm25 + graph each return a ranked list of
``FusedHit``-shaped runs, then we fuse them by rank-only RRF (Cormack et
al., 2009). Rank-only fusion is intentional: the three runs use scores on
different scales (cosine / BM25 / graph relevance) so absolute scores are
incomparable. RRF only consumes ordinal rank.

Score formula:

    score(chunk) = sum_{run i} 1 / (k + rank_i(chunk))

where ``rank_i`` is 1-based position in run ``i``. Constant ``k=60`` is the
Cormack et al. paper default; we expose it for property tests.

Pure, deterministic, no I/O, no dependencies on adapters. Re-used by both
``HybridRetrievalCoordinator`` and the per-strategy wrappers in
``packages/retrieval/strategies/``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from packages.core.models import Chunk
from packages.indexing.protocols import FusedHit, RetrievalSource

DEFAULT_RRF_K: int = 60
MIN_RRF_K: int = 1


def rrf_fuse(
    runs: Sequence[Sequence[tuple[Chunk, float, RetrievalSource]]],
    *,
    k: int = DEFAULT_RRF_K,
    top_n: int | None = None,
) -> list[FusedHit]:
    """Fuse multiple ranked retrieval runs into one RRF-scored list.

    Args:
        runs: Each inner sequence is one run, ordered best-first. Each
            element is ``(chunk, raw_score, source)`` — raw_score is unused
            in fusion (rank-only) but preserved for diagnostics; source
            tags which retrieval route produced the hit (``"vector"`` /
            ``"bm25"`` / ``"graph"`` / ``"community"``).
        k: RRF smoothing constant. Cormack et al. (2009) default is 60.
        top_n: Optional cap on the returned list size; when ``None`` all
            unique chunks across runs are returned.

    Returns:
        List of ``FusedHit`` ordered by descending RRF score. Each hit
        carries ``pre_rerank_rank`` (1-based post-fusion position) and
        the union of ``sources`` that contributed to the chunk.

    Raises:
        ValueError: When ``k`` is below ``MIN_RRF_K``.
    """
    if k < MIN_RRF_K:
        msg = f"RRF k must be >= {MIN_RRF_K}, got {k}"
        raise ValueError(msg)

    if not runs:
        return []

    # Aggregate by chunk_id to dedupe across runs while preserving the
    # first-seen Chunk instance (all runs scoped to one library by callers).
    scores: dict[str, float] = {}
    chunks_by_id: dict[str, Chunk] = {}
    sources_by_id: dict[str, list[RetrievalSource]] = {}

    for run in runs:
        for rank_idx, hit in enumerate(run, start=1):
            chunk, _raw_score, source = hit
            chunk_id = chunk.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank_idx)
            chunks_by_id.setdefault(chunk_id, chunk)
            existing_sources = sources_by_id.setdefault(chunk_id, [])
            if source not in existing_sources:
                existing_sources.append(source)

    # Stable sort: descending score, ties broken by chunk_id for
    # reproducibility (hypothesis property tests rely on this).
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if top_n is not None:
        ranked = ranked[:top_n]

    return [
        FusedHit(
            chunk=chunks_by_id[cid],
            score=score,
            pre_rerank_rank=rank_pos,
            sources=tuple(sources_by_id[cid]),
        )
        for rank_pos, (cid, score) in enumerate(ranked, start=1)
    ]


def runs_from_legacy(
    legacy_runs: Iterable[tuple[Sequence[tuple[Chunk, float]], RetrievalSource]],
) -> list[list[tuple[Chunk, float, RetrievalSource]]]:
    """Adapt legacy ``(chunk, score)`` pairs to source-tagged runs.

    Convenience wrapper used by the upgraded
    :class:`HybridRetrievalCoordinator` so callers that already speak
    ``list[tuple[Chunk, float]]`` can fuse with RRF without restructuring.
    """
    return [[(chunk, score, source) for chunk, score in ranked] for ranked, source in legacy_runs]
