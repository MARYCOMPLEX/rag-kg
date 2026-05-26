"""Tests for SelfRAGCritic — post-generation alignment check (M4.4)."""

from __future__ import annotations

import json

import pytest

from packages.core.models import Chunk
from packages.llm.protocols import LLMResponse, Message
from packages.retrieval.critics import (
    ClaimVerdict,
    SelfRAGAssessment,
    SelfRAGCritic,
    SelfRAGCriticConfig,
    SupportLabel,
)
from packages.retrieval.protocols import RetrievedEvidence


def _chunk(chunk_id: str, text: str = "x") -> Chunk:
    return Chunk(library_id="test-lib", chunk_id=chunk_id, doc_id="d", text=text)


def _evidence(chunk_id: str, text: str = "x", score: float = 0.9) -> RetrievedEvidence:
    return RetrievedEvidence(chunk=_chunk(chunk_id, text), score=score, source="vector")


class FakeLLM:
    """Canned-response fake LLM used to drive critic behaviour deterministically."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(text=self._response, model="fake")


class FakeFailingLLM:
    """Fake LLM that always raises — exercises the fail-open path."""

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        raise RuntimeError("simulated LLM outage")


class TestSelfRAGCriticDefaults:
    @pytest.mark.asyncio
    async def test_empty_answer_short_circuits_to_fail_open(self) -> None:
        # Arrange
        llm = FakeLLM(response="{}")
        critic = SelfRAGCritic(llm)

        # Act
        result = await critic.critique(answer="   ", evidence=[])

        # Assert
        assert isinstance(result, SelfRAGAssessment)
        assert result.overall_support == 1.0
        assert result.verdicts == ()
        assert result.unsupported_claim_count == 0
        assert llm.calls == []  # No LLM call when answer is blank

    @pytest.mark.asyncio
    async def test_empty_evidence_with_answer_still_calls_llm(self) -> None:
        # Arrange
        payload = json.dumps({"claims": []})
        llm = FakeLLM(response=payload)
        critic = SelfRAGCritic(llm)

        # Act
        result = await critic.critique(answer="The sky is blue.", evidence=[])

        # Assert
        assert result.overall_support == 1.0
        assert result.unsupported_claim_count == 0
        assert len(llm.calls) == 1
        # The user prompt should mention the no-evidence sentinel.
        assert "(no evidence retrieved)" in llm.calls[0][1].content


class TestSelfRAGCriticParsing:
    @pytest.mark.asyncio
    async def test_fully_supported_answer_yields_high_overall_support(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "claims": [
                    {
                        "claim": "GraphRAG improves multi-hop QA.",
                        "supporting_chunk_ids": ["c1"],
                        "label": "FULLY_SUPPORTED",
                    },
                    {
                        "claim": "GraphRAG uses community summaries.",
                        "supporting_chunk_ids": ["c2"],
                        "label": "FULLY_SUPPORTED",
                    },
                ]
            }
        )
        critic = SelfRAGCritic(FakeLLM(payload))

        # Act
        result = await critic.critique(
            answer="GraphRAG improves multi-hop QA. It uses community summaries.",
            evidence=[_evidence("c1"), _evidence("c2")],
        )

        # Assert
        assert result.overall_support == 1.0
        assert result.unsupported_claim_count == 0
        assert len(result.verdicts) == 2
        assert all(v.label is SupportLabel.FULLY_SUPPORTED for v in result.verdicts)

    @pytest.mark.asyncio
    async def test_mixed_labels_compute_correct_overall_and_unsupported_count(self) -> None:
        # Arrange — 4 claims: 1 FULLY, 1 PARTIALLY, 1 UNSUPPORTED, 1 CONTRADICTED
        payload = json.dumps(
            {
                "claims": [
                    {
                        "claim": "A",
                        "supporting_chunk_ids": ["c1"],
                        "label": "FULLY_SUPPORTED",
                    },
                    {
                        "claim": "B",
                        "supporting_chunk_ids": ["c1"],
                        "label": "PARTIALLY_SUPPORTED",
                    },
                    {"claim": "C", "supporting_chunk_ids": [], "label": "UNSUPPORTED"},
                    {
                        "claim": "D",
                        "supporting_chunk_ids": ["c2"],
                        "label": "CONTRADICTED",
                    },
                ]
            }
        )
        critic = SelfRAGCritic(FakeLLM(payload))

        # Act
        result = await critic.critique(
            answer="A. B. C. D.",
            evidence=[_evidence("c1"), _evidence("c2")],
        )

        # Assert
        assert len(result.verdicts) == 4
        assert result.overall_support == pytest.approx(0.25)  # 1 of 4 fully supported
        assert result.unsupported_claim_count == 2  # UNSUPPORTED + CONTRADICTED

    @pytest.mark.asyncio
    async def test_invented_chunk_ids_are_filtered(self) -> None:
        # Arrange — model cites a chunk that wasn't in the evidence list
        payload = json.dumps(
            {
                "claims": [
                    {
                        "claim": "Real claim.",
                        "supporting_chunk_ids": ["c1", "ghost", "c2", "c2"],
                        "label": "FULLY_SUPPORTED",
                    }
                ]
            }
        )
        critic = SelfRAGCritic(FakeLLM(payload))

        # Act
        result = await critic.critique(
            answer="Real claim.",
            evidence=[_evidence("c1"), _evidence("c2")],
        )

        # Assert
        assert len(result.verdicts) == 1
        verdict = result.verdicts[0]
        assert verdict.supporting_chunk_ids == ("c1", "c2")  # ghost dropped, c2 dedup'd

    @pytest.mark.asyncio
    async def test_unknown_label_defaults_to_unsupported(self) -> None:
        # Arrange
        payload = json.dumps(
            {
                "claims": [
                    {
                        "claim": "Mystery claim.",
                        "supporting_chunk_ids": [],
                        "label": "TOTALLY_BOGUS_LABEL",
                    }
                ]
            }
        )
        critic = SelfRAGCritic(FakeLLM(payload))

        # Act
        result = await critic.critique(
            answer="Mystery claim.",
            evidence=[_evidence("c1")],
        )

        # Assert
        assert result.verdicts[0].label is SupportLabel.UNSUPPORTED
        assert result.unsupported_claim_count == 1
        assert result.overall_support == 0.0

    @pytest.mark.asyncio
    async def test_response_with_code_fence_still_parses(self) -> None:
        # Arrange — many real LLMs wrap JSON in ```json ... ``` fences
        inner = json.dumps(
            {
                "claims": [
                    {
                        "claim": "Fenced claim.",
                        "supporting_chunk_ids": ["c1"],
                        "label": "FULLY_SUPPORTED",
                    }
                ]
            }
        )
        critic = SelfRAGCritic(FakeLLM(f"```json\n{inner}\n```"))

        # Act
        result = await critic.critique(
            answer="Fenced claim.",
            evidence=[_evidence("c1")],
        )

        # Assert
        assert len(result.verdicts) == 1
        assert result.overall_support == 1.0


class TestSelfRAGCriticFailOpen:
    @pytest.mark.asyncio
    async def test_llm_error_returns_fail_open_assessment(self) -> None:
        # Arrange
        critic = SelfRAGCritic(FakeFailingLLM())

        # Act
        result = await critic.critique(
            answer="Some answer.",
            evidence=[_evidence("c1")],
        )

        # Assert
        assert result.overall_support == 1.0
        assert result.verdicts == ()
        assert result.unsupported_claim_count == 0

    @pytest.mark.asyncio
    async def test_non_json_response_falls_back_to_fail_open(self) -> None:
        # Arrange
        critic = SelfRAGCritic(FakeLLM("the model is having a bad day"))

        # Act
        result = await critic.critique(
            answer="Some answer.",
            evidence=[_evidence("c1")],
        )

        # Assert
        assert result.overall_support == 1.0
        assert result.verdicts == ()

    @pytest.mark.asyncio
    async def test_malformed_json_falls_back_to_fail_open(self) -> None:
        # Arrange — looks like JSON but is invalid
        critic = SelfRAGCritic(FakeLLM('{"claims": [not valid json'))

        # Act
        result = await critic.critique(
            answer="Some answer.",
            evidence=[_evidence("c1")],
        )

        # Assert
        assert result.overall_support == 1.0
        assert result.verdicts == ()


class TestSelfRAGCriticConfig:
    def test_default_config_values(self) -> None:
        # Arrange / Act
        config = SelfRAGCriticConfig()

        # Assert
        assert config.temperature == 0.0
        assert config.max_tokens == 800
        assert config.timeout_s == 60.0

    @pytest.mark.asyncio
    async def test_config_is_passed_through_to_llm(self) -> None:
        # Arrange
        captured: dict[str, object] = {}

        class CapturingLLM:
            async def complete(
                self,
                messages: list[Message],
                *,
                model: str | None = None,
                temperature: float = 0.0,
                max_tokens: int | None = None,
                timeout_s: float = 60.0,
            ) -> LLMResponse:
                captured["temperature"] = temperature
                captured["max_tokens"] = max_tokens
                captured["timeout_s"] = timeout_s
                return LLMResponse(text=json.dumps({"claims": []}), model="fake")

        config = SelfRAGCriticConfig(temperature=0.2, max_tokens=123, timeout_s=7.5)
        critic = SelfRAGCritic(CapturingLLM(), config=config)

        # Act
        await critic.critique(answer="Hello.", evidence=[_evidence("c1")])

        # Assert
        assert captured == {"temperature": 0.2, "max_tokens": 123, "timeout_s": 7.5}


class TestSelfRAGModelsAreFrozen:
    def test_claim_verdict_is_frozen(self) -> None:
        # Arrange
        verdict = ClaimVerdict(
            claim="x",
            supporting_chunk_ids=("c1",),
            label=SupportLabel.FULLY_SUPPORTED,
        )

        # Act / Assert
        with pytest.raises(ValueError, match="frozen"):
            verdict.claim = "y"  # type: ignore[misc]

    def test_assessment_is_frozen(self) -> None:
        # Arrange
        assessment = SelfRAGAssessment(
            overall_support=0.5,
            verdicts=(),
            unsupported_claim_count=0,
        )

        # Act / Assert
        with pytest.raises(ValueError, match="frozen"):
            assessment.overall_support = 0.9  # type: ignore[misc]
