"""ReviewGenerationTask — produces a literature review for a topic.

Pipeline:
1. Outline — LLM proposes 4-8 subtopic headings as JSON.
2. Per-subtopic retrieve + write — for each heading, retrieve evidence
   and ask the LLM to synthesize a 1-2 paragraph section that cites
   chunk_ids inline.
3. Optional abstract — LLM summarizes the assembled sections.

Failures are isolated: an outline failure yields an empty result, and
a single section failure is dropped without aborting the run.

Stage events (ADR-0010): when a `StageEmitter` is supplied via `run(...)`
the task emits ``stage_started`` / ``stage_completed`` events for the
canonical phases — `subtopic_decompose`, `subtopic_local_search`,
`subtopic_draft`, `citation_check`, `final_compose`. The task itself
never imports Redis: the emitter is injected by the worker job.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, cast

from packages.core.models import Query
from packages.llm.protocols import LLMClient, LLMResponse, Message
from packages.orchestration.protocols import (
    Citation,
    ReviewResult,
    ReviewSection,
    TaskBudget,
    TaskCost,
)
from packages.retrieval.protocols import RetrievalPlanner, RetrievedEvidence

# Citation style discriminator. `numeric` produces `[1]`-style markers;
# `author_year` produces `(Author 2024)`-style markers. The body remains
# the LLM-generated `[chunk_id]` text — citation rendering happens in a
# post-process pass so prompts don't need to know the style.
type CitationStyle = Literal["numeric", "author_year"]

# Optional async stage emitter — supplied by the worker job; signature is
# kept tiny so the task layer never has to know about Redis or the bus.
type StageEmitter = Callable[[str, str, dict[str, object]], Awaitable[None]]

_OUTLINE_SYSTEM_PROMPT = """You are planning a literature review. Return strict JSON with the shape:
{"headings": ["First heading", "Second heading", ...]}

Rules:
- Produce 4 to 6 specific subtopic headings (3-7 words each) covering the topic.
- Each heading should be answerable from a retrievable subset of papers.
- Headings must be concrete subtopics, not generic phrases like "Introduction" or "Conclusion".
- Return ONLY JSON, no prose, no markdown fences."""

_OUTLINE_USER_TEMPLATE = """Topic: {topic}

Plan the review outline now."""

_SECTION_SYSTEM_PROMPT = """You are writing one section of a literature review.

Write a 1-2 paragraph section for the given heading using ONLY the provided
evidence chunks. Cite every claim inline with [chunk_id], where chunk_id is
the id shown in brackets next to the evidence text (e.g.,
"GraphRAG uses Leiden clustering [doc::p2::3]").

Rules:
- Be concrete and grounded in the evidence.
- Do NOT invent facts that are not in the evidence.
- Do NOT use introductory phrases like "In this section we discuss".
- If the evidence is insufficient, say so briefly and stop.
- Cite inline, not at the end."""

_SECTION_USER_TEMPLATE = """Section heading: {heading}

Evidence chunks (each prefixed with its chunk_id):

{context}

Write the section now."""

_ABSTRACT_SYSTEM_PROMPT = """You are writing the abstract of a literature review.

Write a 2-3 sentence abstract summarizing the review's main themes, drawn
from the supplied section headings and bodies.

Rules:
- 2 to 3 sentences only.
- No citations in the abstract.
- No first-person phrasing.
- Be concrete: name the main themes, not generic descriptors."""

_ABSTRACT_USER_TEMPLATE = """Topic: {topic}

Sections:

{sections}

Write the abstract now."""


# Permissive citation pattern; we validate against the actual chunk_ids
# returned by the planner before constructing Citation objects.
_CITATION_PATTERN = re.compile(r"\[([a-zA-Z0-9:_\-/.]+)\]")
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_OUTLINE_LINE_RE = re.compile(r"^(?:[-*]\s+|\d{1,2}[.)]\s+)(.+)$")
_HEADING_KEYS = ("headings", "sections", "subtopics", "topics")
_HEADING_ITEM_KEYS = ("heading", "title", "name")

_SECTION_CONCURRENCY = 3
_SNIPPET_LEN = 200


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest JSON object from LLM output."""
    text = _strip_markdown_fence(text)
    if text.startswith("{") and text.endswith("}"):
        return text
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


@dataclass(frozen=True, slots=True)
class ReviewGenerationTaskConfig:
    """Tunables for ReviewGenerationTask."""

    max_sections: int = 6
    chunks_per_section: int = 6
    llm_temperature: float = 0.2
    llm_max_tokens_outline: int = 400
    llm_max_tokens_section: int = 600
    llm_max_tokens_abstract: int = 300
    write_abstract: bool = True
    llm_timeout_s: float = 120.0


@dataclass(frozen=True, slots=True)
class _SectionOutcome:
    """Internal — section result plus its LLM call cost."""

    section: ReviewSection | None
    response: LLMResponse | None


class ReviewGenerationTask:
    """Generate a multi-section literature review for a topic."""

    def __init__(
        self,
        *,
        planner: RetrievalPlanner,
        llm: LLMClient,
        budget: TaskBudget | None = None,
        config: ReviewGenerationTaskConfig | None = None,
    ) -> None:
        self._planner = planner
        self._llm = llm
        self._budget = budget or TaskBudget()
        self._config = config or ReviewGenerationTaskConfig()

    async def run(
        self,
        library_id: str,
        topic: str,
        *,
        citation_style: CitationStyle = "numeric",
        stage_emitter: StageEmitter | None = None,
    ) -> ReviewResult:
        started = time.perf_counter()
        emitter = _coerce_emitter(stage_emitter)

        await emitter("subtopic_decompose", "stage_started", {"topic": topic})
        outline_response, headings = await self._call_outline(topic)
        await emitter(
            "subtopic_decompose",
            "stage_completed",
            {"heading_count": len(headings)},
        )

        if not headings:
            return ReviewResult(
                library_id=library_id,
                topic=topic,
                cost=self._aggregate_cost(
                    [outline_response] if outline_response else [],
                    started,
                ),
            )

        section_cap = min(
            self._config.max_sections,
            self._budget.max_subtopics,
            len(headings),
        )
        capped_headings = headings[:section_cap]

        await emitter(
            "subtopic_local_search",
            "stage_started",
            {"heading_count": len(capped_headings)},
        )
        outcomes = await self._run_sections(library_id, capped_headings, emitter)
        await emitter(
            "subtopic_local_search",
            "stage_completed",
            {"sections_built": sum(1 for o in outcomes if o.section is not None)},
        )

        sections = tuple(o.section for o in outcomes if o.section is not None)
        section_responses = [o.response for o in outcomes if o.response is not None]

        await emitter("citation_check", "stage_started", {})
        sections = _restyle_citations(sections, citation_style)
        await emitter(
            "citation_check",
            "stage_completed",
            {"citation_style": citation_style},
        )

        await emitter("final_compose", "stage_started", {})
        abstract_response, abstract = await self._maybe_call_abstract(topic, sections)
        await emitter(
            "final_compose",
            "stage_completed",
            {"section_count": len(sections), "has_abstract": bool(abstract)},
        )

        all_responses: list[LLMResponse] = []
        if outline_response is not None:
            all_responses.append(outline_response)
        all_responses.extend(section_responses)
        if abstract_response is not None:
            all_responses.append(abstract_response)

        return ReviewResult(
            library_id=library_id,
            topic=topic,
            abstract=abstract,
            sections=sections,
            cost=self._aggregate_cost(all_responses, started),
        )

    # === outline ===

    async def _call_outline(self, topic: str) -> tuple[LLMResponse | None, list[str]]:
        messages = [
            Message(role="system", content=_OUTLINE_SYSTEM_PROMPT),
            Message(role="user", content=_OUTLINE_USER_TEMPLATE.format(topic=topic)),
        ]
        try:
            resp = await self._llm.complete(
                messages,
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_outline,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return None, []
        return resp, _parse_headings(resp.text)

    # === sections ===

    async def _run_sections(
        self,
        library_id: str,
        headings: list[str],
        emitter: StageEmitter,
    ) -> list[_SectionOutcome]:
        sem = asyncio.Semaphore(_SECTION_CONCURRENCY)

        async def _one(heading: str) -> _SectionOutcome:
            async with sem:
                await emitter(
                    "subtopic_draft",
                    "stage_started",
                    {"heading": heading},
                )
                outcome = await self._build_section(library_id, heading)
                await emitter(
                    "subtopic_draft",
                    "stage_completed",
                    {
                        "heading": heading,
                        "has_section": outcome.section is not None,
                    },
                )
                return outcome

        return await asyncio.gather(*(_one(h) for h in headings))

    async def _build_section(self, library_id: str, heading: str) -> _SectionOutcome:
        max_results = min(
            self._config.chunks_per_section,
            self._budget.max_chunks_per_subtopic,
        )
        try:
            retrieval = await self._planner.plan_and_retrieve(
                library_id,
                Query(
                    library_id=library_id,
                    text=heading,
                    type="single-hop",
                    max_results=max_results,
                ),
            )
        except Exception:
            return _SectionOutcome(section=None, response=None)

        evidence = retrieval.evidence[:max_results]
        if not evidence:
            return _SectionOutcome(
                section=ReviewSection(
                    heading=heading,
                    body="No evidence was retrieved for this section.",
                    citations=(),
                    evidence=(),
                ),
                response=None,
            )

        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=_SECTION_SYSTEM_PROMPT),
                    Message(
                        role="user",
                        content=_SECTION_USER_TEMPLATE.format(
                            heading=heading,
                            context=_format_context(evidence),
                        ),
                    ),
                ],
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_section,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return _SectionOutcome(section=None, response=None)

        citations = _extract_citations(resp.text, evidence)
        return _SectionOutcome(
            section=ReviewSection(
                heading=heading,
                body=resp.text,
                citations=tuple(citations),
                evidence=evidence,
            ),
            response=resp,
        )

    # === abstract ===

    async def _maybe_call_abstract(
        self, topic: str, sections: tuple[ReviewSection, ...]
    ) -> tuple[LLMResponse | None, str]:
        if not self._config.write_abstract or not sections:
            return None, ""

        rendered = "\n\n".join(f"## {s.heading}\n{s.body}" for s in sections)
        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=_ABSTRACT_SYSTEM_PROMPT),
                    Message(
                        role="user",
                        content=_ABSTRACT_USER_TEMPLATE.format(topic=topic, sections=rendered),
                    ),
                ],
                temperature=self._config.llm_temperature,
                max_tokens=self._config.llm_max_tokens_abstract,
                timeout_s=self._config.llm_timeout_s,
            )
        except Exception:
            return None, ""
        return resp, resp.text.strip()

    # === cost ===

    @staticmethod
    def _aggregate_cost(responses: list[LLMResponse], started: float) -> TaskCost:
        return TaskCost(
            llm_calls=len(responses),
            input_tokens=sum(r.input_tokens for r in responses),
            output_tokens=sum(r.output_tokens for r in responses),
            cost_usd=sum(r.cost_usd for r in responses),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


def _parse_headings(text: str) -> list[str]:
    """Best-effort parse of real outline output; on failure, return []."""
    for candidate in _outline_json_candidates(text):
        try:
            parsed: object = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        headings = _headings_from_json(parsed)
        if headings:
            return headings

    return _headings_from_lines(text)


def _outline_json_candidates(text: str) -> list[str]:
    clean = _strip_markdown_fence(text)
    candidates: list[str] = []
    if (clean.startswith("{") and clean.endswith("}")) or (
        clean.startswith("[") and clean.endswith("]")
    ):
        candidates.append(clean)
    block = _extract_json_block(clean)
    if block is not None:
        candidates.append(block)
    array_match = _JSON_ARRAY_RE.search(clean)
    if array_match is not None:
        candidates.append(array_match.group(0))

    unique: list[str] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _headings_from_json(parsed: object) -> list[str]:
    if isinstance(parsed, dict):
        mapping = cast("dict[object, object]", parsed)
        for key in _HEADING_KEYS:
            value = mapping.get(key)
            if isinstance(value, list):
                headings = _headings_from_items(cast("list[object]", value))
                if headings:
                    return headings
        return []
    if isinstance(parsed, list):
        return _headings_from_items(cast("list[object]", parsed))
    return []


def _headings_from_items(items: list[object]) -> list[str]:
    raw: list[str] = []
    for item in items:
        if isinstance(item, str):
            raw.append(item)
            continue
        if isinstance(item, dict):
            mapping = cast("dict[object, object]", item)
            for key in _HEADING_ITEM_KEYS:
                value = mapping.get(key)
                if isinstance(value, str):
                    raw.append(value)
                    break
    return _clean_headings(raw)


def _headings_from_lines(text: str) -> list[str]:
    raw: list[str] = []
    for line in _strip_markdown_fence(text).splitlines():
        match = _OUTLINE_LINE_RE.match(line.strip())
        if match is not None:
            raw.append(match.group(1))
    if len(raw) < 2:
        return []
    return _clean_headings(raw)


def _clean_headings(items: list[str]) -> list[str]:
    headings: list[str] = []
    seen: set[str] = set()
    for item in items:
        heading = re.sub(r"^#+\s*", "", item).strip().strip("\"'`")
        heading = heading.rstrip(".:").strip()
        if not heading:
            continue
        key = heading.casefold()
        if key in seen:
            continue
        seen.add(key)
        headings.append(heading)
    return headings


def _format_context(evidence: tuple[RetrievedEvidence, ...]) -> str:
    return "\n\n---\n\n".join(f"[{ev.chunk.chunk_id}] {ev.chunk.text}" for ev in evidence)


def _extract_citations(answer: str, evidence: tuple[RetrievedEvidence, ...]) -> list[Citation]:
    cited_ids = {m.group(1) for m in _CITATION_PATTERN.finditer(answer)}
    by_chunk_id = {ev.chunk.chunk_id: ev for ev in evidence}
    citations: list[Citation] = []
    for chunk_id in cited_ids:
        ev = by_chunk_id.get(chunk_id)
        if ev is None:
            continue
        citations.append(
            Citation(
                chunk_id=ev.chunk.chunk_id,
                doc_id=ev.chunk.doc_id,
                page=ev.chunk.page,
                snippet=ev.chunk.text[:_SNIPPET_LEN],
            )
        )
    return citations


def _coerce_emitter(emitter: StageEmitter | None) -> StageEmitter:
    """Return a real emitter or a no-op fallback.

    Keeps the body of `run()` free of `if emitter is not None` branches.
    """
    if emitter is not None:
        return emitter

    async def _noop(stage: str, event_type: str, payload: dict[str, object]) -> None:
        return None

    return _noop


def _restyle_citations(
    sections: tuple[ReviewSection, ...],
    style: CitationStyle,
) -> tuple[ReviewSection, ...]:
    """Rewrite ``[chunk_id]`` markers in section bodies according to `style`.

    The numeric style emits ``[1]`` / ``[2]`` per the section's citation
    order. The author_year style emits ``(Author Year)`` derived from the
    citation's `doc_id` (split on `::`) — when the doc_id is opaque we
    fall back to ``[chunk_id]`` so the link is preserved.

    `Citation` and `evidence` tuples are unchanged. Bodies are rewritten
    onto fresh `ReviewSection` instances; the original tuple is not
    mutated (CODING_STANDARDS §6).
    """
    out: list[ReviewSection] = []
    for section in sections:
        body = _rewrite_section_body(section, style)
        out.append(section.model_copy(update={"body": body}))
    return tuple(out)


def _rewrite_section_body(section: ReviewSection, style: CitationStyle) -> str:
    if not section.citations:
        return section.body

    by_chunk_id = {c.chunk_id: c for c in section.citations}
    counter: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        chunk_id = match.group(1)
        citation = by_chunk_id.get(chunk_id)
        if citation is None:
            return match.group(0)
        if style == "numeric":
            idx = counter.setdefault(chunk_id, len(counter) + 1)
            return f"[{idx}]"
        # author_year — best-effort parse of `doc_id`. Schema-free; fall
        # through to chunk_id when the metadata isn't present.
        return _format_author_year(citation.doc_id) or match.group(0)

    return _CITATION_PATTERN.sub(_replace, section.body)


def _format_author_year(doc_id: str) -> str:
    """Best-effort `(Author Year)` from `doc_id` (e.g. ``smith2024::p1``)."""
    head = doc_id.split("::", 1)[0]
    match = re.match(r"^([A-Za-z][A-Za-z\-]+)(\d{4})$", head)
    if match is None:
        return ""
    author = match.group(1).capitalize()
    year = match.group(2)
    return f"({author} {year})"
