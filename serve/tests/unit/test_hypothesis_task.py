"""Tests for HypothesisTask — path mining, LLM hypothesis assembly, scoring.

Re-authored after ADR-0020 (`MIN_PATHS_REQUIRED = 2`) — every successful
hypothesis must cite at least two distinct KG paths, and each result is
populated with the three score axes (`novelty / confidence / verifiability`).

The fixtures below construct two parallel paths between `head` and `tail`
so the filter does not strip every candidate. The `_NO_PATH_HYPOTHESIS_STATEMENT`
sentinel kicks in only when path mining returns nothing.
"""
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from packages.core.models import Triple
from packages.llm.protocols import LLMResponse, Message
from packages.orchestration.protocols import Hypothesis
from packages.orchestration.tasks.hypothesis_task import (
    _NO_PATH_HYPOTHESIS_STATEMENT,
    HypothesisTask,
    HypothesisTaskConfig,
)

LIBRARY_ID = "test-lib"


def _triple(head: str, relation: str, tail: str, *, confidence: float = 0.9) -> Triple:
    return Triple(
        library_id=LIBRARY_ID,
        head=head,
        relation=relation,
        tail=tail,
        evidence=("c1",),
        confidence=confidence,
        source_model="test",
    )


def _two_path_neighbors() -> dict[str, list[Triple]]:
    """Build two parallel direct edges so path mining yields ≥ 2 paths.

    Each call to ``get_neighbors(head|tail, depth)`` returns the union of
    all edges so the in-memory ``MultiDiGraph`` ends up with two parallel
    relations between ``head`` and ``tail``.
    """
    triples = [
        _triple("head", "regulates", "tail"),
        _triple("head", "activates", "tail"),
    ]
    return {"head": triples, "tail": triples}


def _multi_hop_neighbors() -> dict[str, list[Triple]]:
    """head →A→ tail and head →B→ tail (two distinct multi-hop paths)."""
    triples = [
        _triple("head", "binds", "A"),
        _triple("A", "produces", "tail"),
        _triple("head", "binds", "B"),
        _triple("B", "produces", "tail"),
    ]
    return {"head": triples, "tail": triples}


class FakeGraphIndex:
    """In-memory GraphIndex returning canned triples per entity."""

    def __init__(self, neighbors: dict[str, list[Triple]] | None = None) -> None:
        self._neighbors = neighbors or {}
        self.calls: list[tuple[str, int]] = []

    async def init_library(self, library_id: str) -> None:
        return None

    async def purge_library(self, library_id: str) -> None:
        return None

    async def upsert_entities(self, library_id: str, entities: object) -> None:
        return None

    async def upsert_triples(self, library_id: str, triples: object) -> None:
        return None

    async def get_neighbors(self, library_id: str, entity_id: str, depth: int = 1) -> list[Triple]:
        self.calls.append((entity_id, depth))
        return list(self._neighbors.get(entity_id, []))


class FakeLLM:
    """LLMClient stub returning a canned response or raising on demand."""

    def __init__(
        self,
        *,
        response_text: str = "{}",
        raises: bool = False,
    ) -> None:
        self._response_text = response_text
        self._raises = raises
        self.last_messages: list[Message] | None = None
        self.call_count: int = 0

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        self.call_count += 1
        self.last_messages = list(messages)
        if self._raises:
            raise RuntimeError("LLM exploded")
        return LLMResponse(
            text=self._response_text,
            model="fake",
            input_tokens=12,
            output_tokens=34,
        )


def _llm_payload(items: Sequence[Mapping[str, object]]) -> str:
    return json.dumps({"hypotheses": [dict(item) for item in items]})


class TestHypothesisTaskPathMining:
    async def test_two_paths_yield_one_hypothesis(self) -> None:
        # Arrange: head and tail directly connected via TWO relations
        # ("regulates" and "activates") so path mining yields 2 paths.
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Head modulates tail through dual edges.",
                        "rationale": "Two parallel relations exist in the KG.",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.8,
                    }
                ]
            )
        )
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        # Act
        result = await task.run(LIBRARY_ID, "head", "tail")

        # Assert
        assert len(result.hypotheses) == 1
        h = result.hypotheses[0]
        assert h.statement == "Head modulates tail through dual edges."
        assert len(h.supporting_paths) == 2
        # Each supporting path must end at "tail" and start at "head".
        for path in h.supporting_paths:
            assert path[0] == "head"
            assert path[-1] == "tail"
        assert h.confidence > 0.0
        assert llm.call_count == 1

    async def test_multi_hop_path_is_discovered(self) -> None:
        # Arrange: head →A→ tail AND head →B→ tail.
        graph_index = FakeGraphIndex(neighbors=_multi_hop_neighbors())
        llm = FakeLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Head triggers tail via two intermediate cofactors.",
                        "rationale": "Two-hop paths through A and B converge at tail.",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.6,
                    }
                ]
            )
        )
        task = HypothesisTask(
            graph_index=graph_index,
            llm=llm,
            config=HypothesisTaskConfig(max_path_depth=3),
        )

        # Act
        result = await task.run(LIBRARY_ID, "head", "tail")

        # Assert
        assert len(result.hypotheses) == 1
        paths = result.hypotheses[0].supporting_paths
        assert len(paths) == 2
        intermediates = {node for path in paths for node in path[2:-1:2]}
        assert intermediates == {"A", "B"}


class TestHypothesisTaskFallbacks:
    async def test_no_path_returns_synthetic_fallback_and_skips_llm(self) -> None:
        # Arrange: disconnected entities — no path exists.
        graph_index = FakeGraphIndex(neighbors={"head": [_triple("head", "binds", "X")]})
        llm = FakeLLM()
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        # Act
        result = await task.run(LIBRARY_ID, "head", "tail")

        # Assert
        assert len(result.hypotheses) == 1
        h = result.hypotheses[0]
        assert h.statement == _NO_PATH_HYPOTHESIS_STATEMENT
        assert h.supporting_paths == ()
        assert llm.call_count == 0
        assert result.cost.llm_calls == 0

    async def test_llm_failure_returns_empty_hypotheses(self) -> None:
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(raises=True)
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        result = await task.run(LIBRARY_ID, "head", "tail")

        assert result.hypotheses == ()
        assert llm.call_count == 1
        assert result.cost.llm_calls == 0  # failed call contributes no cost

    async def test_llm_returns_invalid_json_returns_empty_hypotheses(self) -> None:
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(response_text="not json at all")
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        result = await task.run(LIBRARY_ID, "head", "tail")

        assert result.hypotheses == ()


class TestHypothesisTaskBudget:
    async def test_max_hypotheses_caps_output(self) -> None:
        # Arrange: LLM proposes 5 candidates, each citing both available
        # paths so MIN_PATHS_REQUIRED = 2 is satisfied; config caps at 2.
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        items = [
            {
                "statement": f"Hypothesis {i}.",
                "rationale": "stub",
                "supporting_path_indices": [0, 1],
                "counter_evidence": "",
                "confidence": 0.5,
            }
            for i in range(5)
        ]
        llm = FakeLLM(response_text=_llm_payload(items))
        task = HypothesisTask(
            graph_index=graph_index,
            llm=llm,
            config=HypothesisTaskConfig(max_hypotheses=2),
        )

        result = await task.run(LIBRARY_ID, "head", "tail")

        assert len(result.hypotheses) == 2

    async def test_drops_hypothesis_without_supporting_path(self) -> None:
        # Arrange: LLM returns one valid hypothesis (cites both paths) and
        # one with bogus path indices. Only the valid one survives the
        # ADR-0020 filter (≥ 2 supporting paths).
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Bogus.",
                        "rationale": "",
                        "supporting_path_indices": [99, 100],
                        "counter_evidence": "",
                        "confidence": 0.4,
                    },
                    {
                        "statement": "Real one.",
                        "rationale": "",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.7,
                    },
                ]
            )
        )
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        result = await task.run(LIBRARY_ID, "head", "tail")

        assert len(result.hypotheses) == 1
        assert result.hypotheses[0].statement == "Real one."

    async def test_max_paths_to_explore_caps_path_count(self) -> None:
        # Arrange: many parallel direct relations between head and tail.
        triples = [_triple("head", f"rel_{i}", "tail") for i in range(20)]
        graph_index = FakeGraphIndex(neighbors={"head": triples, "tail": triples})

        captured: dict[str, int] = {}

        class CountingLLM(FakeLLM):
            async def complete(
                self,
                messages: list[Message],
                *,
                model: str | None = None,
                temperature: float = 0.0,
                max_tokens: int | None = None,
                timeout_s: float = 60.0,
            ) -> LLMResponse:
                user_text = messages[1].content
                captured["paths_in_prompt"] = sum(
                    1 for line in user_text.splitlines() if line[:2].rstrip(":").isdigit()
                )
                return await super().complete(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_s=timeout_s,
                )

        llm = CountingLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Stub.",
                        "rationale": "",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.5,
                    }
                ]
            )
        )
        task = HypothesisTask(
            graph_index=graph_index,
            llm=llm,
            config=HypothesisTaskConfig(max_paths_to_explore=5),
        )

        await task.run(LIBRARY_ID, "head", "tail")

        assert captured["paths_in_prompt"] == 5


class TestHypothesisTaskScoring:
    """ADR-0020 three-axis scoring is populated on every returned candidate."""

    async def test_three_axis_scoring_populated(self) -> None:
        # Arrange — two parallel paths, single candidate citing both.
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Dual-edge regulation between head and tail.",
                        "rationale": "Both relations support a unified mechanism.",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.8,
                    }
                ]
            )
        )
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        # Act
        result = await task.run(LIBRARY_ID, "head", "tail")

        # Assert — every axis is in [0, 1].
        assert len(result.hypotheses) == 1
        h = result.hypotheses[0]
        for axis_name in ("novelty", "confidence", "verifiability"):
            value = getattr(h, axis_name)
            assert 0.0 <= value <= 1.0, f"{axis_name}={value} out of [0,1]"
        # Confidence comes from the geomean of underlying path confidences,
        # which are ≥ 0.9 in our fixture, so it must be strictly positive.
        assert h.confidence > 0.0

    async def test_sort_by_novelty_times_confidence(self) -> None:
        # Arrange — two candidates, both passing the MIN_PATHS_REQUIRED
        # filter. We post-process the returned tuple to confirm it is
        # sorted by `novelty × confidence` descending.
        graph_index = FakeGraphIndex(neighbors=_two_path_neighbors())
        llm = FakeLLM(
            response_text=_llm_payload(
                [
                    {
                        "statement": "Candidate A.",
                        "rationale": "",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.4,
                    },
                    {
                        "statement": "Candidate B.",
                        "rationale": "",
                        "supporting_path_indices": [0, 1],
                        "counter_evidence": "",
                        "confidence": 0.9,
                    },
                ]
            )
        )
        task = HypothesisTask(graph_index=graph_index, llm=llm)

        # Act
        result = await task.run(LIBRARY_ID, "head", "tail")

        # Assert — non-empty and monotonically non-increasing in sort_key.
        assert len(result.hypotheses) == 2
        sort_keys = [h.novelty * h.confidence for h in result.hypotheses]
        assert sort_keys == sorted(sort_keys, reverse=True)


def test_no_path_constant_is_stable() -> None:
    """Sanity check — sentinel statement starts with the canonical prefix.

    Regression guard: downstream consumers rely on substring matches
    against `_NO_PATH_HYPOTHESIS_STATEMENT` to surface the "no evidence"
    state in the UI.
    """
    assert isinstance(_NO_PATH_HYPOTHESIS_STATEMENT, str)
    assert "No KG path" in _NO_PATH_HYPOTHESIS_STATEMENT


def test_hypothesis_model_default_score_axes_are_unit_clamped() -> None:
    """`Hypothesis` defaults must satisfy the [0, 1] axis contracts.

    A safety net so future schema tweaks cannot silently drop the bounds
    on the three score axes.
    """
    hypothesis = Hypothesis(statement="placeholder")
    for axis in (hypothesis.novelty, hypothesis.confidence, hypothesis.verifiability):
        assert 0.0 <= axis <= 1.0
