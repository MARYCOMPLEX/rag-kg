"""LLM-based community summarizer.

Generates a short title, 2-3 sentence summary, and 3-5 representative
entity IDs for a KG community. Idempotent w.r.t. its inputs (same
community + entities + triples → same prompt). On any failure the
community is returned unchanged except for `summary="[summary failed]"`
so downstream consumers can still surface the cluster.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.models import Community, Entity, Triple
from packages.llm.protocols import LLMClient, Message

SUMMARY_FAILED_MARKER = "[summary failed]"


class _LLMSummary(BaseModel):
    """Schema for the JSON the LLM is asked to emit."""

    model_config = ConfigDict(extra="ignore")
    title: str = ""
    summary: str = ""
    representative_entities: list[str] = Field(default_factory=list)  # type: ignore[arg-type]


_SYSTEM_PROMPT = """You are a knowledge-graph community summarizer for academic papers.

You receive ENTITIES (with types) and TRIPLES (head -> relation -> tail) that
together form a single densely-connected community of a knowledge graph.

Your job is to produce a compact, human-readable summary that captures the
dominant theme of the community.

Return strict JSON with this shape:
{
  "title": "Short topic label, 3-7 words",
  "summary": "2-3 sentence description of the dominant theme, key methods,
              datasets, or relations in this community.",
  "representative_entities": ["entity_id_1", "entity_id_2", "entity_id_3"]
}

Hard rules:
- title: 3 to 7 words, no trailing punctuation, no markdown.
- summary: 2 to 3 sentences. Stay grounded in the supplied entities/triples.
- representative_entities: 3 to 5 entity_id values copied VERBATIM from the
  ENTITIES list. Pick the ones most central to the community's theme.
- Do not invent entities or relations that are not in the input.
- Return ONLY JSON, no prose, no markdown fences."""

_USER_PROMPT_TEMPLATE = """COMMUNITY: {community_id} (level {level})

ENTITIES (entity_id | name | type):
{entities}

TRIPLES (head -> relation -> tail):
{triples}

Produce the summary JSON now."""


@dataclass(frozen=True, slots=True)
class LLMCommunitySummarizerConfig:
    """Tunables for the LLM community summarizer."""

    max_entities_in_prompt: int = 30
    max_triples_in_prompt: int = 80
    temperature: float = 0.0
    max_tokens: int = 400
    timeout_s: float = 90.0


class LLMCommunitySummarizer:
    """Generate title + summary + representative entities for a community.

    Implements the `CommunitySummarizer` protocol. One LLM call per
    community: cheap relative to extraction, but caller should still
    bound concurrency at the orchestrator level.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        model_name: str,
        config: LLMCommunitySummarizerConfig | None = None,
    ) -> None:
        self._llm = llm
        self._model_name = model_name
        self._config = config or LLMCommunitySummarizerConfig()

    async def summarize(
        self,
        library_id: str,
        community: Community,
        entities: list[Entity],
        triples: list[Triple],
    ) -> Community:
        """Return a copy of `community` with title/summary/reps filled in."""
        # library_id is part of the protocol surface; sanity-check it
        # rather than silently mismatching against community.library_id.
        if community.library_id != library_id:
            return community.model_copy(
                update={
                    "summary": SUMMARY_FAILED_MARKER,
                    "summary_model": self._model_name,
                }
            )

        scoped_entities = self._select_entities(community, entities)
        scoped_triples = self._select_triples(community, scoped_entities, triples)

        if not scoped_entities:
            return community.model_copy(
                update={
                    "summary": SUMMARY_FAILED_MARKER,
                    "summary_model": self._model_name,
                }
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            community_id=community.community_id,
            level=community.level,
            entities=_format_entities(scoped_entities),
            triples=_format_triples(scoped_triples),
        )

        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=_SYSTEM_PROMPT),
                    Message(role="user", content=user_prompt),
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception:
            return community.model_copy(
                update={
                    "summary": SUMMARY_FAILED_MARKER,
                    "summary_model": self._model_name,
                }
            )

        return self._parse_response(community, resp.text, scoped_entities)

    def _select_entities(self, community: Community, entities: list[Entity]) -> list[Entity]:
        members = set(community.member_entity_ids)
        in_community = [e for e in entities if e.entity_id in members]
        in_community.sort(key=lambda e: e.entity_id)
        return in_community[: self._config.max_entities_in_prompt]

    def _select_triples(
        self,
        community: Community,
        scoped_entities: list[Entity],
        triples: list[Triple],
    ) -> list[Triple]:
        scoped_ids = {e.entity_id for e in scoped_entities}
        in_community = [t for t in triples if t.head in scoped_ids and t.tail in scoped_ids]
        in_community.sort(key=lambda t: (t.head, t.relation, t.tail))
        return in_community[: self._config.max_triples_in_prompt]

    def _parse_response(
        self,
        community: Community,
        text: str,
        scoped_entities: list[Entity],
    ) -> Community:
        json_text = _extract_json_block(text)
        if json_text is None:
            return community.model_copy(
                update={
                    "summary": SUMMARY_FAILED_MARKER,
                    "summary_model": self._model_name,
                }
            )
        try:
            payload = _LLMSummary.model_validate_json(json_text)
        except (json.JSONDecodeError, ValidationError):
            return community.model_copy(
                update={
                    "summary": SUMMARY_FAILED_MARKER,
                    "summary_model": self._model_name,
                }
            )

        title = payload.title.strip()
        summary = payload.summary.strip()
        if not summary:
            summary = SUMMARY_FAILED_MARKER

        valid_ids = {e.entity_id for e in scoped_entities}
        representatives = tuple(eid for eid in payload.representative_entities if eid in valid_ids)

        return community.model_copy(
            update={
                "title": title,
                "summary": summary,
                "summary_model": self._model_name,
                "representative_entities": representatives,
            }
        )


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest balanced JSON object from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _format_entities(entities: list[Entity]) -> str:
    return "\n".join(f"- {e.entity_id} | {e.name} | {e.type}" for e in entities)


def _format_triples(triples: list[Triple]) -> str:
    if not triples:
        return "(none)"
    return "\n".join(f"- {t.head} -> {t.relation} -> {t.tail}" for t in triples)
