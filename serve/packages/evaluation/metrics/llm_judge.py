"""LLM-as-judge evaluation metrics.

These metrics call an LLM (and sometimes an embedder) to estimate
qualities like citation faithfulness, answer-claim grounding, and
answer-question relevancy. Each metric makes the smallest possible
number of LLM calls (typically one) to bound cost.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.embedding.protocols import Embedder, Vector
from packages.evaluation.protocols import EvalSample, MetricScore
from packages.llm.protocols import LLMClient, Message
from packages.orchestration.protocols import AnsweredQuery

# === shared helpers ============================================================

_CITATION_RE = re.compile(r"\[([a-zA-Z0-9:_\-/.]+)\]")
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest balanced JSON object from LLM output.

    Copied locally to avoid cross-package siblings dependency.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine similarity between two equal-length float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _safe_error_score(metric_name: str, judge_model: str, err: str) -> MetricScore:
    """Build a 0.0 MetricScore wrapping an LLM/judge failure."""
    return MetricScore(
        metric_name=metric_name,
        score=0.0,
        judge_model=judge_model,
        error=err,
    )


_MIN_RELEVANCY_VECTORS = 2


def _parse_judge_payload[T: BaseModel](
    text: str, model_cls: type[T]
) -> tuple[T | None, str | None]:
    """Extract a JSON block from LLM text and validate against model_cls.

    Returns (payload, None) on success or (None, error_message) on failure.
    """
    json_text = _extract_json_block(text)
    if json_text is None:
        return None, "judge returned no JSON block"
    try:
        return model_cls.model_validate_json(json_text), None
    except (json.JSONDecodeError, ValidationError) as exc:
        return None, f"json parse: {exc}"


# === CitationF1 ================================================================

_CITATION_F1_PROMPT = """You are a citation auditor. For each cited chunk in an answer,
decide whether the chunk text actually supports the claim immediately preceding the citation.

ANSWER:
{answer}

CITED CHUNKS:
{chunks}

For every chunk_id, output JSON of the form:
{{
  "judgements": [
    {{"chunk_id": "doc::p1::3", "supports": true, "reason": "matches claim X"}}
  ]
}}

Rules:
- Only include chunk_ids that appear in CITED CHUNKS.
- supports=true ONLY when the chunk explicitly grounds the preceding claim.
- Return ONLY JSON, no prose, no markdown fences."""


class _CitationJudgement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chunk_id: str
    supports: bool
    reason: str = ""


class _CitationJudgePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    judgements: list[_CitationJudgement] = Field(default_factory=list)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class CitationF1Config:
    """Tunables for CitationF1Metric."""

    max_tokens: int = 1500
    temperature: float = 0.0
    timeout_s: float = 60.0


class CitationF1Metric:
    """Precision/Recall/F1 of citations grounded in retrieved evidence.

    - cited_ids: chunk_ids extracted from the answer text.
    - retrieved_ids: chunk_ids actually retrieved.
    - LLM judges, for each cited chunk that was retrieved, whether the chunk
      supports the immediately-preceding claim.
    Score = F1 of supported-and-cited chunks vs. retrieved-and-relevant chunks.
    """

    def __init__(
        self,
        llm: LLMClient,
        judge_model: str = "judge",
        config: CitationF1Config | None = None,
    ) -> None:
        self._llm = llm
        self._judge_model = judge_model
        self._config = config or CitationF1Config()

    @property
    def name(self) -> str:
        return "citation_f1"

    @property
    def requires_judge(self) -> bool:
        return True

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        del sample
        cited_ids = tuple(dict.fromkeys(_CITATION_RE.findall(answered.answer)))
        if not cited_ids:
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                details={
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "cited": 0,
                    "supported": 0,
                },
            )

        chunks_by_id = {ev.chunk.chunk_id: ev.chunk for ev in answered.retrieved}
        cited_with_text = [
            (cid, chunks_by_id[cid].text) for cid in cited_ids if cid in chunks_by_id
        ]
        if not cited_with_text:
            # All citations are dangling — none correspond to retrieved chunks.
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                details={
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "cited": len(cited_ids),
                    "supported": 0,
                    "dangling": len(cited_ids),
                },
            )

        chunks_block = "\n\n---\n\n".join(
            f"[chunk_id={cid}]\n{text}" for cid, text in cited_with_text
        )
        prompt = _CITATION_F1_PROMPT.format(answer=answered.answer, chunks=chunks_block)
        try:
            resp = await self._llm.complete(
                [Message(role="user", content=prompt)],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception as exc:
            return _safe_error_score(self.name, self._judge_model, str(exc))

        payload, err = _parse_judge_payload(resp.text, _CitationJudgePayload)
        if payload is None:
            return _safe_error_score(self.name, self._judge_model, err or "parse error")

        valid_ids = {cid for cid, _ in cited_with_text}
        supported_ids = {
            j.chunk_id for j in payload.judgements if j.supports and j.chunk_id in valid_ids
        }

        # Precision = supported / cited (penalises dangling and unsupported cites)
        precision = len(supported_ids) / max(1, len(cited_ids))
        # Recall = supported / retrieved (penalises low-coverage answers)
        recall = len(supported_ids) / max(1, len(chunks_by_id)) if chunks_by_id else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return MetricScore(
            metric_name=self.name,
            score=f1,
            judge_model=self._judge_model,
            cost_usd=resp.cost_usd,
            details={
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "cited": len(cited_ids),
                "supported": len(supported_ids),
                "retrieved": len(chunks_by_id),
            },
        )


# === Faithfulness =============================================================

_FAITHFULNESS_PROMPT = """You are a faithfulness judge (Ragas-style).

Step 1: decompose the ANSWER into atomic factual CLAIMS.
Step 2: for each claim, decide whether it is supported by EVIDENCE.

ANSWER:
{answer}

EVIDENCE (retrieved chunks):
{evidence}

Output JSON of the form:
{{
  "claims": [
    {{"claim": "X is the SOTA model", "supported": true}}
  ]
}}

Rules:
- A claim is supported ONLY if the evidence explicitly states or directly implies it.
- Skip subjective language; capture factual statements.
- Return ONLY JSON, no prose, no markdown fences."""


class _FaithClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim: str
    supported: bool


class _FaithPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claims: list[_FaithClaim] = Field(default_factory=list)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class FaithfulnessConfig:
    """Tunables for FaithfulnessMetric."""

    max_tokens: int = 1500
    temperature: float = 0.0
    timeout_s: float = 60.0
    max_evidence_chars: int = 8000


class FaithfulnessMetric:
    """Ragas-style faithfulness: #supported_claims / #total_claims.

    Single LLM call decomposes claims AND judges support to bound cost.
    """

    def __init__(
        self,
        llm: LLMClient,
        judge_model: str = "judge",
        config: FaithfulnessConfig | None = None,
    ) -> None:
        self._llm = llm
        self._judge_model = judge_model
        self._config = config or FaithfulnessConfig()

    @property
    def name(self) -> str:
        return "faithfulness"

    @property
    def requires_judge(self) -> bool:
        return True

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        del sample
        if not answered.answer.strip():
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                details={"claims": 0, "supported": 0},
            )

        evidence_block = self._build_evidence_block(answered)
        if not evidence_block:
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                details={"claims": 0, "supported": 0, "no_evidence": True},
            )

        prompt = _FAITHFULNESS_PROMPT.format(answer=answered.answer, evidence=evidence_block)
        try:
            resp = await self._llm.complete(
                [Message(role="user", content=prompt)],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception as exc:
            return _safe_error_score(self.name, self._judge_model, str(exc))

        payload, err = _parse_judge_payload(resp.text, _FaithPayload)
        if payload is None:
            return _safe_error_score(self.name, self._judge_model, err or "parse error")

        total = len(payload.claims)
        if total == 0:
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                cost_usd=resp.cost_usd,
                details={"claims": 0, "supported": 0},
            )
        supported = sum(1 for c in payload.claims if c.supported)
        score_value = supported / total
        return MetricScore(
            metric_name=self.name,
            score=score_value,
            judge_model=self._judge_model,
            cost_usd=resp.cost_usd,
            details={"claims": total, "supported": supported},
        )

    def _build_evidence_block(self, answered: AnsweredQuery) -> str:
        if not answered.retrieved:
            return ""
        budget = self._config.max_evidence_chars
        used = 0
        parts: list[str] = []
        for ev in answered.retrieved:
            piece = f"[chunk_id={ev.chunk.chunk_id}]\n{ev.chunk.text}"
            if used + len(piece) > budget and parts:
                break
            parts.append(piece)
            used += len(piece)
        return "\n\n---\n\n".join(parts)


# === AnswerRelevancy ===========================================================

_ANSWER_RELEVANCY_PROMPT = """Given an ANSWER, generate exactly 3 hypothetical
QUESTIONS that this answer would naturally and directly answer. The questions
should be specific, well-formed, and stand on their own.

ANSWER:
{answer}

Output JSON of the form:
{{
  "questions": ["q1", "q2", "q3"]
}}

Return ONLY JSON, no prose, no markdown fences."""


class _RelevancyPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    questions: list[str] = Field(default_factory=list)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class AnswerRelevancyConfig:
    """Tunables for AnswerRelevancyMetric."""

    num_questions: int = 3
    max_tokens: int = 600
    temperature: float = 0.3
    timeout_s: float = 60.0


class AnswerRelevancyMetric:
    """Mean cosine similarity between embedding of original Q and embeddings
    of hypothetical Qs the LLM thinks the answer would address.

    Single LLM call + one batched embedding call to bound cost.
    """

    def __init__(
        self,
        llm: LLMClient,
        embedder: Embedder,
        judge_model: str = "judge",
        config: AnswerRelevancyConfig | None = None,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._judge_model = judge_model
        self._config = config or AnswerRelevancyConfig()

    @property
    def name(self) -> str:
        return "answer_relevancy"

    @property
    def requires_judge(self) -> bool:
        return True

    def _questions_from_payload(self, text: str) -> tuple[list[str] | None, str | None]:
        payload, err = _parse_judge_payload(text, _RelevancyPayload)
        if payload is None:
            return None, err
        hypothetical = [q.strip() for q in payload.questions if q.strip()]
        if not hypothetical:
            return None, "no hypothetical questions generated"
        return hypothetical, None

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        del sample
        question = answered.question.strip()
        if not question or not answered.answer.strip():
            return MetricScore(
                metric_name=self.name,
                score=0.0,
                judge_model=self._judge_model,
                details={"reason": "empty question or answer"},
            )

        prompt = _ANSWER_RELEVANCY_PROMPT.format(answer=answered.answer)
        try:
            resp = await self._llm.complete(
                [Message(role="user", content=prompt)],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception as exc:
            return _safe_error_score(self.name, self._judge_model, str(exc))

        hypothetical, err = self._questions_from_payload(resp.text)
        if hypothetical is None:
            return _safe_error_score(self.name, self._judge_model, err or "parse error")

        try:
            vectors = await self._embedder.embed([question, *hypothetical])
        except Exception as exc:
            return _safe_error_score(self.name, self._judge_model, f"embed: {exc}")

        if len(vectors) < _MIN_RELEVANCY_VECTORS:
            return _safe_error_score(
                self.name, self._judge_model, "embedder returned too few vectors"
            )

        q_vec = vectors[0]
        sims = [_cosine_similarity(q_vec, v) for v in vectors[1:]]
        # cosine in [-1, 1]; clamp to [0, 1] for MetricScore
        clamped = [max(0.0, min(1.0, s)) for s in sims]
        mean_score = sum(clamped) / len(clamped)
        details: Mapping[str, object] = {
            "num_questions": len(hypothetical),
            "similarities": tuple(sims),
        }
        return MetricScore(
            metric_name=self.name,
            score=mean_score,
            judge_model=self._judge_model,
            cost_usd=resp.cost_usd,
            details=details,
        )
