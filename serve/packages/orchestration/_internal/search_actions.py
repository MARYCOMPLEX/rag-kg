"""Static action registry for the ⌘K palette (ADR-0023 §7).

Why static: v1 actions count <20, hot-reload not needed, and a hard-coded
tuple gives zero-DB cold start + grep-friendly maintenance. Plug-in
extensibility is a v2 concern (PRD §15.2).

Visibility rule: actions with `requires_library=True` are only matched
when the caller passes a non-empty `library_id`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from packages.orchestration.search import SearchHit


@dataclass(frozen=True, slots=True)
class Action:
    """One row in the action registry."""

    id: str
    title: str
    subtitle: str | None
    keywords: tuple[str, ...]
    deeplink_template: str
    requires_library: bool = False


ACTIONS: tuple[Action, ...] = (
    Action(
        id="open_chat",
        title="Open Chat",
        subtitle="Start a new conversation in this library",
        keywords=("chat", "qa", "ask", "question"),
        deeplink_template="/lib/{library_id}/chat",
        requires_library=True,
    ),
    Action(
        id="generate_review",
        title="Generate Literature Review",
        subtitle="Run a review task on this library",
        keywords=("review", "survey", "literature", "summary"),
        deeplink_template="/lib/{library_id}/review/new",
        requires_library=True,
    ),
    Action(
        id="open_kg",
        title="Open Knowledge Graph",
        subtitle="Explore the KG of this library",
        keywords=("kg", "graph", "knowledge"),
        deeplink_template="/lib/{library_id}/kg",
        requires_library=True,
    ),
    Action(
        id="open_eval",
        title="Open Eval Dashboard",
        subtitle="View VAR / Citation F1 / cost trends",
        keywords=("eval", "evaluation", "metrics", "var", "kpi"),
        deeplink_template="/lib/{library_id}/eval",
        requires_library=True,
    ),
    Action(
        id="settings_global",
        title="Open Global Settings",
        subtitle="Configure backend, LLM, embedder",
        keywords=("settings", "config", "preference"),
        deeplink_template="/settings",
        requires_library=False,
    ),
    Action(
        id="library_create",
        title="Create New Library",
        subtitle="Add a new research library",
        keywords=("new", "create", "library"),
        deeplink_template="/libraries/new",
        requires_library=False,
    ),
    Action(
        id="open_documents",
        title="Open Documents",
        subtitle="Browse documents in this library",
        keywords=("docs", "documents", "papers", "files"),
        deeplink_template="/lib/{library_id}/docs",
        requires_library=True,
    ),
    Action(
        id="open_hypothesize",
        title="Generate Hypotheses",
        subtitle="Run hypothesis generation on entity pairs",
        keywords=("hypothesis", "hypothesize", "novel", "ideas"),
        deeplink_template="/lib/{library_id}/hypothesize",
        requires_library=True,
    ),
    Action(
        id="switch_library",
        title="Switch Library",
        subtitle="Choose another research library",
        keywords=("switch", "library", "change"),
        deeplink_template="/libraries",
        requires_library=False,
    ),
)


def _score_action_match(action: Action, q_lower: str) -> float:
    """Cheap keyword overlap score in [0, 1].

    Token-level: count how many of the user's tokens appear (substring) in
    the action's title or any of its keywords.
    """
    tokens = [t for t in q_lower.split() if t]
    if not tokens:
        return 0.0
    haystacks = (action.title.lower(), *(k.lower() for k in action.keywords))
    matched = sum(1 for t in tokens if any(t in h for h in haystacks))
    if matched == 0:
        return 0.0
    return min(matched / len(tokens), 1.0)


def search_actions(
    q: str,
    *,
    library_id: str | None,
    limit: int,
) -> tuple[tuple[SearchHit, ...], int]:
    """Match the static action registry against `q`.

    Returns: `(hits, duration_ms)`.
    """
    started = time.monotonic()
    q_lower = q.strip().lower()
    if not q_lower:
        return (), 0
    hits: list[SearchHit] = []
    for action in ACTIONS:
        if action.requires_library and not library_id:
            continue
        score = _score_action_match(action, q_lower)
        if score == 0.0:
            continue
        deeplink = (
            action.deeplink_template.format(library_id=library_id)
            if "{library_id}" in action.deeplink_template
            else action.deeplink_template
        )
        hits.append(
            SearchHit(
                type="action",
                id=action.id,
                title=action.title,
                subtitle=action.subtitle,
                library_id=None,
                score=score,
                payload={
                    "deeplink": deeplink,
                    "keywords": list(action.keywords),
                    "requires_library": action.requires_library,
                },
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    duration_ms = int((time.monotonic() - started) * 1000)
    return tuple(hits[:limit]), duration_ms
