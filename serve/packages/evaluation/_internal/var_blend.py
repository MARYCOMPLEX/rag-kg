"""Pure VAR blend function (ADR-0016 §3).

Isolates the linear-ramp formula from any I/O so it can be exercised
with property-based tests without spinning up a Postgres or LLM.
"""

from __future__ import annotations

# Linear ramp constants (ADR-0016 §3 — Constants).
N_FEEDBACK_FULL_TRUST: int = 30
N_FEEDBACK_DISPLAY_MIN: int = 5
DEFAULT_WINDOW_DAYS: int = 7
JUDGE_AGREEMENT_THRESHOLD: float = 0.6
MIN_SAMPLE_SIZE_FOR_ALERT: int = 30


def blend(
    var_feedback: float | None,
    var_judge: float | None,
    n_feedback: int,
    *,
    n_full_trust: int = N_FEEDBACK_FULL_TRUST,
) -> float:
    """Blend feedback-derived and judge-derived VAR.

    Formula (ADR-0016 §3):
        w_fb = min(1, n_feedback / n_full_trust)
        var_blended = w_fb * var_feedback + (1 - w_fb) * var_judge

    Fallback rules (not in §3, follow from §1's "feedback-priority + judge-fallback"):
        * If both inputs are None -> 0.0 (neither tier had data; surfaced as
          empty in the API layer).
        * If `var_feedback` is None or `n_feedback == 0` -> return `var_judge` (or 0.0).
        * If `var_judge` is None -> return `var_feedback` weighted only by w_fb;
          when w_fb < 1 the missing judge contribution is treated as 0.0
          to preserve the conservative semantics of "missing data".

    Args:
        var_feedback: Mean of `useful AND citations_correct` over user feedback,
            in `[0, 1]`. None when no feedback rows exist.
        var_judge: Mean of LLM-judge agreed verdicts, in `[0, 1]`. None when
            judge has not run for the window.
        n_feedback: Count of feedback rows in the window. Drives the weight.
        n_full_trust: Sample count at which `w_fb = 1.0`. Default per ADR-0016.

    Returns:
        Blended VAR in `[0, 1]`.

    Raises:
        ValueError: If `n_feedback < 0` or `n_full_trust <= 0` or any input is
            outside `[0, 1]`.
    """
    if n_feedback < 0:
        msg = f"n_feedback must be >= 0, got {n_feedback}"
        raise ValueError(msg)
    if n_full_trust <= 0:
        msg = f"n_full_trust must be > 0, got {n_full_trust}"
        raise ValueError(msg)
    _validate_unit_or_none(var_feedback, "var_feedback")
    _validate_unit_or_none(var_judge, "var_judge")

    if var_feedback is None and var_judge is None:
        return 0.0
    if var_feedback is None or n_feedback == 0:
        return float(var_judge) if var_judge is not None else 0.0
    if var_judge is None:
        # Conservative: missing judge contributes 0 weighted by (1 - w_fb).
        weight_fb = min(1.0, n_feedback / n_full_trust)
        return weight_fb * float(var_feedback)

    weight_fb = min(1.0, n_feedback / n_full_trust)
    weight_judge = 1.0 - weight_fb
    return weight_fb * float(var_feedback) + weight_judge * float(var_judge)


def _validate_unit_or_none(value: float | None, name: str) -> None:
    if value is None:
        return
    if not 0.0 <= value <= 1.0:
        msg = f"{name} must be in [0, 1], got {value}"
        raise ValueError(msg)


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "JUDGE_AGREEMENT_THRESHOLD",
    "MIN_SAMPLE_SIZE_FOR_ALERT",
    "N_FEEDBACK_DISPLAY_MIN",
    "N_FEEDBACK_FULL_TRUST",
    "blend",
]
