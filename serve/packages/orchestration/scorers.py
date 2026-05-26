"""Hypothesis three-axis scoring (ADR-0020).

Pure, side-effect-free functions for the novelty / confidence / verifiability
axes of a hypothesis. These are deliberately isolated from the LLM call,
the KG path-mining, and the cache layer so they can be:

- Property-tested with `hypothesis` (every input → score in [0, 1]; monotone
  in the obvious dimension)
- Reused by the calibration script (`data/calibration/hypothesis/*.json`)
- Cheap to call (no I/O; numpy-free; ~ µs each)

The integration point is `score_hypothesis(library_id, hypothesis, paths)`,
which builds a fresh frozen `Hypothesis` populated with the three axes. The
underlying numerical helpers (`score_novelty`, `score_confidence`,
`score_verifiability`) are public so unit tests and reviewers can exercise
each axis independently.

Reference set selection (the embeddings that drive `score_novelty`) lives
upstream — the scorer takes pre-computed reference embeddings as a tuple of
floats per row. The novelty cache (per-library, 24 h TTL) is owned by the
hypothesis worker job. See ADR-0020 §1.4.

Sort key (`novelty * confidence`) is exported as `hypothesis_sort_key` so
callers don't have to remember the formula. Verifiability is intentionally
*not* in the sort — see ADR-0020 §2.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from packages.core.models import Entity
from packages.orchestration.protocols import Hypothesis, ReasoningPath

# ----------------------------------------------------------------------
# Constants — see ADR-0020 §1
# ----------------------------------------------------------------------

#: Entity labels treated as "verifiable" components on a path. See
#: ADR-0020 §1.3 for the rationale; users can extend in v1.1 via
#: per-Library config.
METHOD_DATASET_LABELS: frozenset[str] = frozenset({"Method", "Dataset", "Benchmark", "Metric"})

#: Path-density saturation point. 4 paths is "many", >4 buys nothing.
_PATH_DENSITY_SATURATION = 4.0

#: Verifiability weighting (method-ratio vs path-density). 0.8 / 0.2 from
#: ADR-0020 §1.3, calibrated monthly.
_VERIF_METHOD_WEIGHT = 0.8
_VERIF_DENSITY_WEIGHT = 0.2

#: Default novelty when there is no baseline to compare against.
_NOVELTY_DEFAULT_NO_BASELINE = 0.5

#: Minimum number of supporting paths a candidate must have to be
#: returned to the user (PRD §12.5). This is a *filter*, not a score.
MIN_PATHS_REQUIRED = 2


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _clamp_unit(x: float) -> float:
    """Clamp a real number into the [0, 1] interval."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 on degenerate inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    num = 0.0
    sum_a = 0.0
    sum_b = 0.0
    for x, y in zip(a, b, strict=True):
        num += x * y
        sum_a += x * x
        sum_b += y * y
    denom = math.sqrt(sum_a) * math.sqrt(sum_b)
    if denom <= 0.0:
        return 0.0
    return num / denom


def _percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile.

    `pct` in [0, 100]. Empty input returns 0.0. The simpler nearest-rank
    rule is fine here: we use it only as a robust min-max anchor and we
    never rely on the precise value for downstream comparisons.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if pct <= 0.0:
        return sorted_vals[0]
    if pct >= 100.0:
        return sorted_vals[-1]
    rank = math.ceil(pct / 100.0 * len(sorted_vals)) - 1
    rank = max(rank, 0)
    if rank >= len(sorted_vals):
        rank = len(sorted_vals) - 1
    return sorted_vals[rank]


def _pairwise_distances(refs: Sequence[Sequence[float]]) -> list[float]:
    """Cosine distances between all unordered pairs of reference embeddings."""
    out: list[float] = []
    n = len(refs)
    for i in range(n):
        for j in range(i + 1, n):
            out.append(1.0 - _cosine_similarity(refs[i], refs[j]))
    return out


# ----------------------------------------------------------------------
# Per-axis scorers
# ----------------------------------------------------------------------


def score_novelty(
    candidate_embedding: Sequence[float],
    reference_embeddings: Sequence[Sequence[float]],
) -> float:
    """Novelty = mean cosine distance from the per-Library baseline, min-max
    normalised against the baseline's internal distance distribution.

    See ADR-0020 §1.1.

    Args:
        candidate_embedding: The hypothesis statement embedded once.
        reference_embeddings: Pre-computed embeddings for the per-Library
            reference set (community summaries / chunk claims). Capped to
            ~200 by the caller to keep this O(n).

    Returns:
        A float in [0, 1]. Returns the neutral default 0.5 when no
        baseline exists (cold-start library) or the candidate vector is
        degenerate.
    """
    if not reference_embeddings or not candidate_embedding:
        return _NOVELTY_DEFAULT_NO_BASELINE

    distances = [1.0 - _cosine_similarity(candidate_embedding, ref) for ref in reference_embeddings]
    raw = sum(distances) / len(distances)

    # Anchor on the baseline's *own* distance distribution. Otherwise a
    # uniformly novel domain (e.g. brand-new library) makes everything
    # score 1.0; min-max keeps the relative ordering stable.
    pairwise = _pairwise_distances(reference_embeddings)
    if not pairwise:
        return _clamp_unit(raw / 2.0)  # cosine distance lives in [0, 2]
    p10 = _percentile(pairwise, 10.0)
    p90 = _percentile(pairwise, 90.0)
    spread = max(p90 - p10, 1e-6)
    return _clamp_unit((raw - p10) / spread)


def score_confidence(paths: Sequence[ReasoningPath]) -> float:
    """Confidence = geometric mean of path confidences.

    Geometric mean is sensitive to weak links — a single 0.2 path drags
    the score down hard, matching the "evidence chain is as strong as its
    weakest link" intuition. See ADR-0020 §1.2.

    Returns:
        A float in [0, 1]. Returns 0.0 when no valid paths exist (those
        candidates should already have been filtered out upstream by
        `MIN_PATHS_REQUIRED`).
    """
    if not paths:
        return 0.0
    valid = [p.confidence for p in paths if 0.0 < p.confidence <= 1.0]
    if not valid:
        return 0.0
    # geomean = exp(mean(log(c))). All `c` are > 0 by the filter above.
    log_sum = sum(math.log(c) for c in valid)
    return _clamp_unit(math.exp(log_sum / len(valid)))


def score_verifiability(paths: Sequence[ReasoningPath]) -> float:
    """Verifiability = 0.8 × method/dataset node ratio + 0.2 × path density.

    See ADR-0020 §1.3 for rationale and weight choices.

    Returns:
        A float in [0, 1]. Returns 0.0 when there are no paths or no
        nodes on any path (ill-formed input).
    """
    if not paths:
        return 0.0

    total_nodes = 0
    method_nodes = 0
    for path in paths:
        for node in path.nodes:
            total_nodes += 1
            if _is_method_or_dataset(node):
                method_nodes += 1

    method_ratio = 0.0 if total_nodes == 0 else method_nodes / total_nodes

    path_density = min(len(paths) / _PATH_DENSITY_SATURATION, 1.0)

    raw = method_ratio * _VERIF_METHOD_WEIGHT + path_density * _VERIF_DENSITY_WEIGHT
    return _clamp_unit(raw)


def _is_method_or_dataset(entity: Entity) -> bool:
    """Treat both `type` and `label` style metadata as candidates.

    `Entity.type` is a free-form string in `packages/core/models.py`; we
    accept any case-insensitive match against the canonical labels.
    """
    return entity.type.strip() in METHOD_DATASET_LABELS or any(
        entity.type.strip().casefold() == label.casefold() for label in METHOD_DATASET_LABELS
    )


# ----------------------------------------------------------------------
# Composite scoring
# ----------------------------------------------------------------------


def hypothesis_sort_key(hypothesis: Hypothesis) -> float:
    """Sort key for ranking hypotheses.

    `novelty × confidence` per ADR-0020 §2 — verifiability is intentionally
    *not* part of the sort key.
    """
    return hypothesis.novelty * hypothesis.confidence


def score_hypothesis(
    library_id: str,
    hypothesis: Hypothesis,
    paths: Sequence[ReasoningPath],
    *,
    candidate_embedding: Sequence[float] | None = None,
    reference_embeddings: Sequence[Sequence[float]] | None = None,
) -> Hypothesis:
    """Return a fresh `Hypothesis` populated with all three score axes.

    The original `hypothesis` is not mutated (CODING_STANDARDS §6).

    Args:
        library_id: Used only for the per-library validation contract;
            the scorer itself does not perform any cross-library lookup
            since both the candidate embedding and the reference set are
            already library-scoped by the caller.
        hypothesis: The pre-scored candidate (rationale + supporting_paths
            should already be set by the LLM step).
        paths: Structured KG paths; used to compute confidence and
            verifiability. May be empty — the candidate will then score
            zero on those two axes (filter upstream).
        candidate_embedding: Pre-computed embedding of the hypothesis
            statement. When `None`, novelty falls back to the neutral
            default 0.5.
        reference_embeddings: Per-library baseline. When empty/None,
            novelty falls back to the neutral default 0.5.

    Returns:
        A new `Hypothesis` with novelty / confidence / verifiability
        filled in. Existing fields (`statement`, `rationale`,
        `supporting_paths`, `counter_evidence`) are preserved.
    """
    if not library_id:
        msg = "score_hypothesis requires a non-empty library_id"
        raise ValueError(msg)

    if candidate_embedding is None or reference_embeddings is None:
        novelty = _NOVELTY_DEFAULT_NO_BASELINE
    else:
        novelty = score_novelty(candidate_embedding, reference_embeddings)

    confidence = score_confidence(paths)
    verifiability = score_verifiability(paths)

    return hypothesis.model_copy(
        update={
            "novelty": novelty,
            "confidence": confidence,
            "verifiability": verifiability,
        }
    )


__all__ = [
    "METHOD_DATASET_LABELS",
    "MIN_PATHS_REQUIRED",
    "hypothesis_sort_key",
    "score_confidence",
    "score_hypothesis",
    "score_novelty",
    "score_verifiability",
]
