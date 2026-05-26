"""Token budgeting helpers for the context subsystem.

`CharCountTokenCounter` provides a fast char/4 heuristic that is acceptable
for budgeting decisions (off by ≤10% on natural English; conservative for
CJK because chars-per-token there is closer to 1.0 — i.e., we *over*-count
which is the safe direction for a budget).

`trim_to_tokens` is the workhorse used by `PromptComposer` to fit individual
slots: it trims by character approximation and tries to preserve the last
sentence boundary so the trimmed text reads cleanly.
"""

from __future__ import annotations

from packages.context.protocols import TokenCounter

# Chars-per-token heuristic. English averages ~4 chars/token under BPE;
# CJK is closer to 1, so this counter over-counts CJK (safe for budgets).
_CHARS_PER_TOKEN = 4

# Sentence terminators we try to preserve when trimming. Order matters
# only insofar as the *latest* match within the cut region wins.
_SENTENCE_TERMINATORS = (". ", "? ", "! ", "。", "？", "！", "\n\n")  # noqa: RUF001

# Below this many tokens, we don't bother hunting for a sentence boundary —
# the text is too small to matter and any cut is fine.
_MIN_TOKENS_FOR_BOUNDARY_SEARCH = 8


class CharCountTokenCounter:
    """Char/4 token counter — fast and dependency-free.

    Implements the `TokenCounter` Protocol structurally; no inheritance.
    """

    def count(self, text: str) -> int:
        if not text:
            return 0
        # ceil-division so a 1-char string still counts as 1 token.
        return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


def trim_to_tokens(text: str, max_tokens: int, counter: TokenCounter) -> str:
    """Trim `text` so its token count ≤ `max_tokens`.

    Tries to cut at the last sentence boundary within the budget when one
    exists; otherwise cuts at the char-approximation boundary directly.
    Returns the input unchanged when already within budget or when
    `max_tokens <= 0` and the text is empty.

    Args:
        text: The text to potentially trim.
        max_tokens: Hard upper bound on the result's token count.
        counter: TokenCounter used to verify the result.

    Returns:
        A possibly-trimmed copy of `text`. Never longer than the input.
    """
    if max_tokens <= 0:
        return ""
    if counter.count(text) <= max_tokens:
        return text

    # Char-approximate cut point. We do NOT call `counter.count` in a loop
    # because the heuristic is monotone w.r.t. length; one shot is enough.
    cut = max_tokens * _CHARS_PER_TOKEN
    if cut >= len(text):
        return text

    candidate = text[:cut]
    if max_tokens < _MIN_TOKENS_FOR_BOUNDARY_SEARCH:
        return candidate

    boundary = _find_last_sentence_boundary(candidate)
    if boundary is not None:
        return candidate[:boundary]
    return candidate


def _find_last_sentence_boundary(text: str) -> int | None:
    """Return the index *after* the last sentence terminator, or None.

    Only considers terminators in the second half of `text` so we don't
    discard most of the slot in the name of a clean cut.
    """
    half = len(text) // 2
    best: int | None = None
    for term in _SENTENCE_TERMINATORS:
        idx = text.rfind(term)
        if idx >= half:
            end = idx + len(term)
            if best is None or end > best:
                best = end
    return best
