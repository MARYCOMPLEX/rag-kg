"""Retrieval critics: relevance graders that decide if evidence is good enough.

This module hosts lightweight LLM-based critics used by agentic retrieval
planners (M4). A critic inspects a query + retrieved evidence and emits a
structured judgement that a planner can use to branch (re-retrieve, fall
back, or answer as-is).
"""

# === CRAGEvaluator (M4.3) — by agent A ===

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.llm.protocols import LLMClient, Message
from packages.retrieval.protocols import RetrievedEvidence


class GradeLabel(StrEnum):
    """Three-way relevance verdict from Yan et al. 2024 (Corrective RAG)."""

    CORRECT = "CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    INCORRECT = "INCORRECT"


class EvidenceGrade(BaseModel):
    """Per-chunk relevance grade emitted by the CRAG evaluator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    label: GradeLabel
    reason: str = ""


class CRAGAssessment(BaseModel):
    """Aggregated CRAG verdict over a batch of retrieved chunks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall: GradeLabel
    grades: tuple[EvidenceGrade, ...] = ()
    trigger_rewrite: bool = False


@dataclass(frozen=True, slots=True)
class CRAGEvaluatorConfig:
    """Tunables for the CRAG relevance grader."""

    correct_threshold: float = 0.7
    incorrect_threshold: float = 0.3
    temperature: float = 0.0
    max_tokens: int = 600
    timeout_s: float = 60.0


class _LLMGradeItem(BaseModel):
    """Single grading row as returned by the LLM."""

    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=0)
    score: float
    label: str = ""
    reason: str = ""


_SYSTEM_PROMPT = """You are a strict relevance grader for retrieval-augmented generation.

You will receive a USER QUERY and a numbered list of retrieved CHUNKS.
Score how well each chunk on its own helps answer the query.

Scoring rubric (float in [0.0, 1.0]):
  - 0.8-1.0  HIGH relevance — directly answers or contains the key fact
  - 0.4-0.79 PARTIAL relevance — related context, supporting detail, or topical
  - 0.0-0.39 LOW relevance — off-topic, tangential, or irrelevant

Label each chunk with exactly one of: CORRECT, AMBIGUOUS, INCORRECT.
Use CORRECT for HIGH, AMBIGUOUS for PARTIAL, INCORRECT for LOW.

Return ONLY a JSON array (no prose, no markdown fences) shaped like:
[
  {"index": 0, "score": 0.85, "label": "CORRECT", "reason": "states the answer"},
  {"index": 1, "score": 0.20, "label": "INCORRECT", "reason": "different topic"}
]

Hard rules:
- One object per input chunk, in the same order, using the chunk's index.
- score MUST be a float between 0.0 and 1.0 inclusive.
- label MUST be one of CORRECT, AMBIGUOUS, INCORRECT.
- reason MUST be a short phrase (<= 20 words)."""

_USER_PROMPT_TEMPLATE = """USER QUERY:
{query}

CHUNKS:
{chunks}

Grade every chunk now and return the JSON array."""


class CRAGEvaluator:
    """LLM-based relevance grader implementing the CRAG critic step.

    One batched LLM call grades all retrieved chunks at once. The aggregate
    verdict tells a planner whether to (a) answer with the evidence as-is,
    (b) ensemble with caution, or (c) trigger a rewrite + re-retrieve.
    """

    def __init__(
        self,
        llm: LLMClient,
        config: CRAGEvaluatorConfig | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or CRAGEvaluatorConfig()

    async def evaluate(self, query: str, evidence: list[RetrievedEvidence]) -> CRAGAssessment:
        """Grade evidence for query-relevance and aggregate to a CRAG verdict."""
        if not evidence:
            return CRAGAssessment(overall=GradeLabel.AMBIGUOUS, grades=(), trigger_rewrite=False)

        chunks_block = self._format_chunks(evidence)
        user = _USER_PROMPT_TEMPLATE.format(query=query, chunks=chunks_block)

        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=_SYSTEM_PROMPT),
                    Message(role="user", content=user),
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception:
            # Fail open: on LLM failure, return a neutral verdict
            return CRAGAssessment(overall=GradeLabel.AMBIGUOUS, grades=(), trigger_rewrite=False)

        grades = self._parse_response(resp.text, evidence)
        return self._aggregate(grades)

    @staticmethod
    def _format_chunks(evidence: list[RetrievedEvidence]) -> str:
        return "\n\n---\n\n".join(
            f"[index={i}] [chunk_id={ev.chunk.chunk_id}]\n{ev.chunk.text}"
            for i, ev in enumerate(evidence)
        )

    def _parse_response(
        self, text: str, evidence: list[RetrievedEvidence]
    ) -> tuple[EvidenceGrade, ...]:
        json_text = _extract_json_block(text)
        if json_text is None:
            return ()

        try:
            raw = json.loads(json_text)
        except json.JSONDecodeError:
            return ()
        if not isinstance(raw, list):
            return ()

        items: list[_LLMGradeItem] = []
        for entry in raw:  # pyright: ignore[reportUnknownVariableType]
            try:
                items.append(_LLMGradeItem.model_validate(entry))
            except ValidationError:
                continue

        out: list[EvidenceGrade] = []
        for item in items:
            if item.index < 0 or item.index >= len(evidence):
                continue
            score = max(0.0, min(1.0, float(item.score)))
            label = self._label_from_score(score, item.label)
            chunk_id = evidence[item.index].chunk.chunk_id
            out.append(
                EvidenceGrade(
                    chunk_id=chunk_id,
                    score=score,
                    label=label,
                    reason=item.reason.strip()[:200],
                )
            )
        return tuple(out)

    def _label_from_score(self, score: float, raw_label: str) -> GradeLabel:
        normalized = raw_label.strip().upper()
        if normalized in GradeLabel.__members__:
            return GradeLabel[normalized]
        # Fallback: derive label from score using configured thresholds
        if score >= self._config.correct_threshold:
            return GradeLabel.CORRECT
        if score < self._config.incorrect_threshold:
            return GradeLabel.INCORRECT
        return GradeLabel.AMBIGUOUS

    def _aggregate(self, grades: tuple[EvidenceGrade, ...]) -> CRAGAssessment:
        if not grades:
            return CRAGAssessment(overall=GradeLabel.AMBIGUOUS, grades=(), trigger_rewrite=False)

        scores = [g.score for g in grades]
        max_score = max(scores)
        if max_score >= self._config.correct_threshold:
            overall = GradeLabel.CORRECT
        elif all(s < self._config.incorrect_threshold for s in scores):
            overall = GradeLabel.INCORRECT
        else:
            overall = GradeLabel.AMBIGUOUS

        # Trigger rewrite when no chunk reached the CORRECT bar.
        trigger_rewrite = overall == GradeLabel.INCORRECT or (
            overall == GradeLabel.AMBIGUOUS
            and all(s < self._config.correct_threshold for s in scores)
        )

        return CRAGAssessment(overall=overall, grades=grades, trigger_rewrite=trigger_rewrite)


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest JSON array from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_ARRAY_RE.search(text)
    if match is None:
        return None
    return match.group(0)


# === END CRAGEvaluator ===


# === SelfRAGCritic (M4.4) — by agent B ===

_SELF_RAG_SYSTEM_PROMPT = """You are a strict factuality auditor for a retrieval-augmented \
generation system.

You will be given:
1. An ANSWER produced by another model.
2. A list of EVIDENCE chunks, each tagged with a unique chunk_id.

Your job is to:
1. Decompose the ANSWER into atomic factual claims (one verifiable proposition each).
2. For every claim, list the chunk_ids from EVIDENCE that directly support it (may be empty).
3. Label the claim with EXACTLY ONE of:
   - FULLY_SUPPORTED      — every part of the claim is entailed by the cited chunks.
   - PARTIALLY_SUPPORTED  — only some of the claim is grounded; the rest is unverified.
   - UNSUPPORTED          — no chunk provides evidence for the claim.
   - CONTRADICTED         — at least one chunk directly contradicts the claim.

Return ONLY valid JSON in this exact shape, with no prose, no markdown fences:
{
  "claims": [
    {
      "claim": "<one atomic claim from the answer>",
      "supporting_chunk_ids": ["<chunk_id>", "..."],
      "label": "FULLY_SUPPORTED"
    }
  ]
}

Hard rules:
- Use ONLY chunk_ids that appear in the EVIDENCE block. Never invent ids.
- If the answer has no factual content, return {"claims": []}.
- Prefer fewer well-formed claims over many overlapping ones.
- Be conservative: when unsure, prefer PARTIALLY_SUPPORTED or UNSUPPORTED over \
FULLY_SUPPORTED."""

_SELF_RAG_USER_PROMPT_TEMPLATE = """ANSWER:
{answer}

EVIDENCE:
{evidence}

Audit the answer now and return JSON."""

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class SupportLabel(StrEnum):
    """Per-claim grounding verdict from the Self-RAG critic."""

    FULLY_SUPPORTED = "FULLY_SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class ClaimVerdict(BaseModel):
    """A single decomposed claim with its grounding label and supporting chunks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str
    supporting_chunk_ids: tuple[str, ...]
    label: SupportLabel


class SelfRAGAssessment(BaseModel):
    """Aggregated Self-RAG critique of an answer against retrieved evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_support: float = Field(ge=0.0, le=1.0)
    verdicts: tuple[ClaimVerdict, ...]
    unsupported_claim_count: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class SelfRAGCriticConfig:
    """Tunables for the Self-RAG post-generation critic."""

    temperature: float = 0.0
    max_tokens: int = 800
    timeout_s: float = 60.0


class _RawClaim(BaseModel):
    """Loose schema for a single claim row from the LLM JSON response."""

    model_config = ConfigDict(extra="ignore")

    claim: str
    supporting_chunk_ids: list[str] = Field(default_factory=list)  # type: ignore[arg-type]
    label: str


class _RawCritique(BaseModel):
    """Top-level wrapper for parsed Self-RAG JSON."""

    model_config = ConfigDict(extra="ignore")

    claims: list[_RawClaim] = Field(default_factory=list)  # type: ignore[arg-type]


def _self_rag_fail_open() -> SelfRAGAssessment:
    """Neutral assessment used when the critic cannot run or parse a response.

    The Self-RAG critic is best-effort and never blocks generation, so on any
    failure we assume the answer is fine (overall_support=1.0, no claims).
    """
    return SelfRAGAssessment(
        overall_support=1.0,
        verdicts=(),
        unsupported_claim_count=0,
    )


def _extract_json_object(text: str) -> str | None:
    """Best-effort extraction of the largest JSON object in an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _format_self_rag_evidence(evidence: list[RetrievedEvidence]) -> str:
    """Render evidence chunks for the critic prompt with stable tags."""
    if not evidence:
        return "(no evidence retrieved)"
    parts: list[str] = []
    for item in evidence:
        chunk = item.chunk
        parts.append(f"[chunk_id={chunk.chunk_id}]\n{chunk.text}")
    return "\n\n".join(parts)


def _coerce_support_label(raw: str) -> SupportLabel:
    """Map an arbitrary LLM label string to a known SupportLabel.

    Falls back to UNSUPPORTED when the model emits an unknown token —
    that is the safer default for a factuality auditor.
    """
    normalized = raw.strip().upper().replace("-", "_").replace(" ", "_")
    try:
        return SupportLabel(normalized)
    except ValueError:
        return SupportLabel.UNSUPPORTED


def _build_verdicts(
    raw_claims: list[_RawClaim],
    valid_chunk_ids: frozenset[str],
) -> tuple[ClaimVerdict, ...]:
    """Build immutable ClaimVerdict tuples, dropping invented chunk_ids."""
    out: list[ClaimVerdict] = []
    for raw in raw_claims:
        claim_text = raw.claim.strip()
        if not claim_text:
            continue
        seen: set[str] = set()
        kept: list[str] = []
        for cid in raw.supporting_chunk_ids:
            if cid in valid_chunk_ids and cid not in seen:
                seen.add(cid)
                kept.append(cid)
        out.append(
            ClaimVerdict(
                claim=claim_text,
                supporting_chunk_ids=tuple(kept),
                label=_coerce_support_label(raw.label),
            )
        )
    return tuple(out)


def _summarize_verdicts(verdicts: tuple[ClaimVerdict, ...]) -> SelfRAGAssessment:
    """Compute overall_support and unsupported_claim_count from verdicts."""
    if not verdicts:
        return _self_rag_fail_open()
    fully = sum(1 for v in verdicts if v.label is SupportLabel.FULLY_SUPPORTED)
    unsupported = sum(
        1 for v in verdicts if v.label in (SupportLabel.UNSUPPORTED, SupportLabel.CONTRADICTED)
    )
    overall = fully / len(verdicts)
    return SelfRAGAssessment(
        overall_support=overall,
        verdicts=verdicts,
        unsupported_claim_count=unsupported,
    )


class SelfRAGCritic:
    """Post-generation alignment check inspired by Self-RAG (Asai et al. 2023).

    Simulates the ISREL + ISSUP reflection tokens via a single prompt-based
    critique that decomposes the answer into atomic claims and labels each
    claim's grounding against the retrieved evidence. On any LLM or parse
    failure the critic fails open with overall_support=1.0 — it is advisory,
    never gating.
    """

    def __init__(
        self,
        llm: LLMClient,
        config: SelfRAGCriticConfig | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or SelfRAGCriticConfig()

    async def critique(
        self,
        answer: str,
        evidence: list[RetrievedEvidence],
    ) -> SelfRAGAssessment:
        """Critique ``answer`` against ``evidence`` and return an assessment."""
        if not answer.strip():
            return _self_rag_fail_open()

        messages = [
            Message(role="system", content=_SELF_RAG_SYSTEM_PROMPT),
            Message(
                role="user",
                content=_SELF_RAG_USER_PROMPT_TEMPLATE.format(
                    answer=answer.strip(),
                    evidence=_format_self_rag_evidence(evidence),
                ),
            ),
        ]

        try:
            response = await self._llm.complete(
                messages,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception:
            # Fail open: never block the surrounding planner on critic errors.
            return _self_rag_fail_open()

        json_text = _extract_json_object(response.text)
        if json_text is None:
            return _self_rag_fail_open()

        try:
            payload = json.loads(json_text)
            critique = _RawCritique.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            return _self_rag_fail_open()

        valid_ids = frozenset(item.chunk.chunk_id for item in evidence)
        verdicts = _build_verdicts(critique.claims, valid_ids)
        return _summarize_verdicts(verdicts)


# === END SelfRAGCritic ===
