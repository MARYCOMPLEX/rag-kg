"""QueryRouter — heuristic classifier deciding local vs global retrieval.

The router inspects the query text and decides whether to route to:
- "local"  — chunk-level retrieval (DirectRAG / CoordinatorRAG)
- "global" — community-summary retrieval (GlobalRAGPlanner)

Pure heuristics for the M3 baseline: no LLM call, no async, no I/O.
A future M4+ iteration may upgrade to LLM-based routing.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

# Words that strongly suggest a high-level / corpus-wide question.
GLOBAL_SIGNAL_WORDS: Final[tuple[str, ...]] = (
    "overall",
    "main",
    "common",
    "summary",
    "summarize",
    "summarise",
    "trend",
    "trends",
    "categories",
    "category",
    "types of",
    "what kind",
    "what kinds",
    "landscape",
    "themes",
    "theme",
    "overview",
    "high-level",
    "across the",
    # Chinese signals
    "整体",
    "主要",
    "概览",
    "趋势",
    "归类",
    "类型",
)

# Patterns that strongly suggest a focused / entity-specific question.
LOCAL_SIGNAL_PATTERNS: Final[tuple[str, ...]] = (
    r"\bwhat\s+is\s+\w+",
    r"\bwho\s+is\s+\w+",
    r"\bwhen\s+(?:did|was|were)\b",
    r"\bwhere\s+(?:is|did|was)\b",
    r"\bhow\s+does\s+\w+\s+work\b",
    r"\bdefine\s+\w+",
    r"\bdefinition\s+of\s+\w+",
)

LONG_QUERY_WORD_THRESHOLD: Final[int] = 12
GLOBAL_DECISION_THRESHOLD: Final[float] = 0.5
GLOBAL_SIGNAL_WEIGHT: Final[float] = 0.5
LONG_QUERY_WEIGHT: Final[float] = 0.25
LOCAL_SIGNAL_WEIGHT: Final[float] = 0.6

Route = Literal["local", "global"]


class RouteDecision(BaseModel):
    """The router's verdict for a query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    route: Route
    reason: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class QueryRouter:
    """Heuristic local-vs-global query router (no LLM, no I/O)."""

    def __init__(
        self,
        *,
        global_signal_words: tuple[str, ...] = GLOBAL_SIGNAL_WORDS,
        local_signal_patterns: tuple[str, ...] = LOCAL_SIGNAL_PATTERNS,
        long_query_threshold: int = LONG_QUERY_WORD_THRESHOLD,
        decision_threshold: float = GLOBAL_DECISION_THRESHOLD,
    ) -> None:
        self._global_words = tuple(w.lower() for w in global_signal_words)
        self._local_patterns = tuple(re.compile(p, re.IGNORECASE) for p in local_signal_patterns)
        self._long_query_threshold = long_query_threshold
        self._decision_threshold = decision_threshold

    def classify(self, query_text: str) -> RouteDecision:
        """Classify a raw query into a routing decision.

        The score reflects confidence in the *global* direction:
        - score >= threshold  → global
        - score <  threshold  → local
        """
        text = query_text.strip()
        if not text:
            return RouteDecision(
                route="local",
                reason="empty query defaults to local",
                score=0.0,
            )

        lower = text.lower()
        word_count = len(text.split())

        global_hits = tuple(w for w in self._global_words if w in lower)
        local_hits = tuple(p.pattern for p in self._local_patterns if p.search(text) is not None)
        is_long_query = word_count > self._long_query_threshold

        global_score = 0.0
        if global_hits:
            global_score += GLOBAL_SIGNAL_WEIGHT
        if is_long_query:
            global_score += LONG_QUERY_WEIGHT
        if local_hits:
            global_score -= LOCAL_SIGNAL_WEIGHT

        clamped = max(0.0, min(1.0, global_score))
        route: Route = "global" if clamped >= self._decision_threshold else "local"
        reason = _format_reason(
            route=route,
            global_hits=global_hits,
            local_hits=local_hits,
            is_long_query=is_long_query,
            word_count=word_count,
        )
        return RouteDecision(route=route, reason=reason, score=clamped)


def _format_reason(
    *,
    route: Route,
    global_hits: tuple[str, ...],
    local_hits: tuple[str, ...],
    is_long_query: bool,
    word_count: int,
) -> str:
    """Build a human-readable explanation for the routing decision."""
    parts: list[str] = [f"route={route}"]
    if global_hits:
        parts.append(f"global_signals={list(global_hits)}")
    if local_hits:
        parts.append(f"local_signals={list(local_hits)}")
    if is_long_query:
        parts.append(f"long_query(words={word_count})")
    if not global_hits and not local_hits and not is_long_query:
        parts.append("no_strong_signals")
    return "; ".join(parts)
