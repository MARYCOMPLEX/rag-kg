"""LLM-based query rewriter for retrieval ensembling.

Implements three battle-tested rewrite strategies:

- HyDE (Gao et al., 2022) — generate a hypothetical answer document and
  use that as the retrieval query. Embeds tend to align better with
  candidate passages than with the raw question.
- step_back (Zhou et al., 2024) — abstract the question to a higher-level
  principle / mechanism, retrieve broader background first.
- decompose — break a multi-part question into a single narrower
  sub-question (just the first sub-q) so callers can run an ensemble.

The rewriter always emits the original query as a `passthrough` entry
first so that downstream callers can fuse rewritten + original recall.
On any LLM failure for a strategy we fall back to a passthrough entry
for that strategy — never raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.llm.protocols import LLMClient, Message

Strategy = Literal["hyde", "step_back", "decompose", "passthrough"]

_SUPPORTED_STRATEGIES: Final[frozenset[str]] = frozenset({"hyde", "step_back", "decompose"})

_HYDE_SYSTEM_PROMPT: Final[str] = (
    "You are a hypothetical-document generator for dense retrieval (HyDE).\n"
    "Given a user QUESTION, write a SHORT 2-3 sentence passage that reads "
    "like an authoritative answer and would directly contain the information "
    "needed.\n"
    "Do not hedge, do not refuse, do not add citations or quotes.\n"
    "Output ONLY the passage text — no preamble, no labels, no markdown."
)

_STEP_BACK_SYSTEM_PROMPT: Final[str] = (
    "You are a step-back question rewriter (Zhou et al., 2024).\n"
    "Given a SPECIFIC question, produce ONE more general question that "
    "asks about the underlying principle, mechanism, or category behind it.\n"
    "The step-back question must be answerable independently of the original "
    "specifics and useful for retrieving broad background context.\n"
    "Output ONLY the rewritten question on a single line — no preamble."
)

_DECOMPOSE_SYSTEM_PROMPT: Final[str] = (
    "You are a query decomposer for multi-hop retrieval.\n"
    "Given a complex QUESTION that may have multiple parts or hops, output "
    "ONLY the FIRST narrower sub-question that should be answered first.\n"
    "The sub-question must be self-contained, answerable on its own, and "
    "strictly narrower than the original.\n"
    "Output ONLY the sub-question on a single line — no numbering, no "
    "preamble, no extra sub-questions."
)

_USER_PROMPT_TEMPLATE: Final[str] = "QUESTION:\n{query}"


class RewrittenQuery(BaseModel):
    """A single rewrite produced by one strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original: str
    rewritten: str
    strategy: Strategy
    rationale: str = ""


class RewriteSet(BaseModel):
    """Bundle of rewrites for a single original query (always 1+)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original: str
    queries: tuple[RewrittenQuery, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class QueryRewriterConfig:
    """Tunables for the LLM query rewriter."""

    temperature: float = 0.3
    max_tokens: int = 200
    timeout_s: float = 60.0
    strategies: tuple[str, ...] = field(default=("hyde",))


def _system_prompt_for(strategy: str) -> str:
    if strategy == "hyde":
        return _HYDE_SYSTEM_PROMPT
    if strategy == "step_back":
        return _STEP_BACK_SYSTEM_PROMPT
    if strategy == "decompose":
        return _DECOMPOSE_SYSTEM_PROMPT
    msg = f"unsupported strategy: {strategy!r}"
    raise ValueError(msg)


def _passthrough(
    original: str,
    strategy: Strategy = "passthrough",
    rationale: str = "",
) -> RewrittenQuery:
    return RewrittenQuery(
        original=original,
        rewritten=original,
        strategy=strategy,
        rationale=rationale,
    )


class LLMQueryRewriter:
    """Generates retrieval-friendly query rewrites via an LLM.

    Always returns a `RewriteSet` where the first entry is the original
    query as a `passthrough`, followed by one rewrite per configured
    strategy. Strategies that fail at the LLM layer degrade gracefully
    to a passthrough entry tagged with that strategy's name in the
    rationale (so callers can still see ensemble cardinality).
    """

    def __init__(
        self,
        llm: LLMClient,
        config: QueryRewriterConfig | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or QueryRewriterConfig()
        self._validate_strategies(self._config.strategies)

    @staticmethod
    def _validate_strategies(strategies: tuple[str, ...]) -> None:
        for s in strategies:
            if s not in _SUPPORTED_STRATEGIES:
                msg = f"unsupported strategy {s!r}; supported: {sorted(_SUPPORTED_STRATEGIES)}"
                raise ValueError(msg)

    async def rewrite(self, query: str) -> RewriteSet:
        """Produce passthrough + one rewrite per configured strategy."""
        original = query.strip()
        rewrites: list[RewrittenQuery] = [_passthrough(original)]

        for strategy in self._config.strategies:
            rewrites.append(await self._rewrite_one(original, strategy))

        return RewriteSet(original=original, queries=tuple(rewrites))

    async def _rewrite_one(self, query: str, strategy: str) -> RewrittenQuery:
        try:
            system = _system_prompt_for(strategy)
        except ValueError:
            return _passthrough(
                query,
                strategy="passthrough",
                rationale=f"unsupported strategy {strategy!r}",
            )

        user = _USER_PROMPT_TEMPLATE.format(query=query)
        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=system),
                    Message(role="user", content=user),
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception as exc:
            return _passthrough(
                query,
                strategy="passthrough",
                rationale=f"{strategy} failed: {type(exc).__name__}",
            )

        text = resp.text.strip()
        if not text:
            return _passthrough(
                query,
                strategy="passthrough",
                rationale=f"{strategy} returned empty text",
            )

        # We know strategy was validated above — narrow for the type checker.
        narrowed: Strategy
        if strategy == "hyde":
            narrowed = "hyde"
        elif strategy == "step_back":
            narrowed = "step_back"
        else:
            narrowed = "decompose"

        return RewrittenQuery(
            original=query,
            rewritten=text,
            strategy=narrowed,
            rationale=f"{strategy} rewrite",
        )
