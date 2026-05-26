"""Tests for the Langfuse-traced LLM wrapper.

We stub out the `langfuse` module entirely with `unittest.mock` so the
tests do not require the real SDK to be importable, and so we can
deterministically assert the wrapper's behavior under simulated failures.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.llm.protocols import LLMResponse, Message
from packages.observability.langfuse_client import (
    LangfuseConfig,
    LangfuseTracedLLM,
    update_config,
    with_library_tag,
)


def _fake_response(text: str = "ok") -> LLMResponse:
    return LLMResponse(
        text=text,
        model="test-model",
        input_tokens=3,
        output_tokens=2,
    )


def _make_inner(text: str = "ok") -> AsyncMock:
    inner = AsyncMock()
    inner.complete = AsyncMock(return_value=_fake_response(text))
    inner.close = AsyncMock(return_value=None)
    return inner


def _install_fake_langfuse_module(
    *,
    raise_on_init: bool = False,
    raise_on_start: bool = False,
    raise_on_flush: bool = False,
) -> tuple[ModuleType, MagicMock, MagicMock]:
    """Install a fake `langfuse` module into sys.modules.

    Returns (module, Langfuse_class_mock, generation_mock) so tests can
    introspect calls without importing the real SDK.
    """
    generation = MagicMock(name="LangfuseGeneration")
    if raise_on_start:
        generation_factory = MagicMock(side_effect=RuntimeError("boom-start"))
    else:
        generation_factory = MagicMock(return_value=generation)

    client_instance = MagicMock(name="LangfuseClient")
    client_instance.start_observation = generation_factory
    if raise_on_flush:
        client_instance.flush = MagicMock(side_effect=RuntimeError("boom-flush"))
    else:
        client_instance.flush = MagicMock()

    if raise_on_init:
        langfuse_cls = MagicMock(side_effect=RuntimeError("boom-init"))
    else:
        langfuse_cls = MagicMock(return_value=client_instance)

    module = ModuleType("langfuse")
    module.Langfuse = langfuse_cls  # type: ignore[attr-defined]
    sys.modules["langfuse"] = module
    return module, langfuse_cls, generation


@pytest.fixture(autouse=True)
def _cleanup_langfuse_module() -> Any:
    """Ensure each test starts with no fake `langfuse` module installed."""
    sys.modules.pop("langfuse", None)
    yield
    sys.modules.pop("langfuse", None)


class TestConfig:
    def test_defaults(self) -> None:
        config = LangfuseConfig()
        assert config.enabled is False
        assert config.host == "http://localhost:3000"
        assert config.flush_at == 10
        assert config.flush_interval_s == 5.0

    def test_update_config_returns_new_instance(self) -> None:
        original = LangfuseConfig()
        updated = update_config(original, enabled=True, public_key="pk")
        assert original.enabled is False  # original untouched
        assert updated.enabled is True
        assert updated.public_key == "pk"


class TestPassThroughDisabled:
    @pytest.mark.asyncio
    async def test_disabled_does_not_import_langfuse(self) -> None:
        # Arrange
        inner = _make_inner("hello")
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=False),
        )

        # Act: patch the import machinery so any langfuse import would fail loudly.
        with patch.dict(sys.modules, {"langfuse": None}):
            result = await wrapper.complete([Message(content="hi")])

        # Assert
        assert result.text == "hello"
        inner.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disabled_close_only_closes_inner(self) -> None:
        inner = _make_inner()
        wrapper = LangfuseTracedLLM(inner=inner, config=LangfuseConfig(enabled=False))
        await wrapper.close()
        inner.close.assert_awaited_once()


class TestEnabledHappyPath:
    @pytest.mark.asyncio
    async def test_enabled_records_generation(self) -> None:
        _, langfuse_cls, generation = _install_fake_langfuse_module()
        inner = _make_inner("answer")
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True, public_key="pk", secret_key="sk"),
            default_tags=["env:test"],
        )

        result = await wrapper.complete(
            [Message(content="hi")],
            model="m",
            temperature=0.5,
            max_tokens=128,
        )

        assert result.text == "answer"
        # Lazy init happened exactly once.
        langfuse_cls.assert_called_once()
        # Generation start + update + end were called.
        client = langfuse_cls.return_value
        client.start_observation.assert_called_once()
        start_kwargs = client.start_observation.call_args.kwargs
        assert start_kwargs["as_type"] == "generation"
        assert start_kwargs["model"] == "m"
        assert start_kwargs["model_parameters"]["temperature"] == 0.5
        assert start_kwargs["metadata"]["tags"] == ["env:test"]
        generation.update.assert_called_once()
        update_kwargs = generation.update.call_args.kwargs
        assert update_kwargs["output"] == "answer"
        assert update_kwargs["usage_details"] == {"input": 3, "output": 2}
        assert "latency_ms" in update_kwargs["metadata"]
        generation.end.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_init_only_runs_once_across_calls(self) -> None:
        _, langfuse_cls, _ = _install_fake_langfuse_module()
        wrapper = LangfuseTracedLLM(
            inner=_make_inner(),
            config=LangfuseConfig(enabled=True),
        )
        await wrapper.complete([Message(content="x")])
        await wrapper.complete([Message(content="y")])
        assert langfuse_cls.call_count == 1


class TestEnabledFailureModes:
    @pytest.mark.asyncio
    async def test_init_failure_returns_inner_result(self) -> None:
        _install_fake_langfuse_module(raise_on_init=True)
        inner = _make_inner("still-works")
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )
        result = await wrapper.complete([Message(content="hi")])
        assert result.text == "still-works"
        inner.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_generation_failure_does_not_block(self) -> None:
        _install_fake_langfuse_module(raise_on_start=True)
        inner = _make_inner("survives")
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )
        result = await wrapper.complete([Message(content="hi")])
        assert result.text == "survives"

    @pytest.mark.asyncio
    async def test_inner_exception_still_ends_generation_then_propagates(self) -> None:
        _, _langfuse_cls, generation = _install_fake_langfuse_module()
        inner = AsyncMock()
        inner.complete = AsyncMock(side_effect=ValueError("inner fail"))
        inner.close = AsyncMock()
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )

        with pytest.raises(ValueError, match="inner fail"):
            await wrapper.complete([Message(content="hi")])

        generation.end.assert_called_once()
        update_kwargs = generation.update.call_args.kwargs
        assert update_kwargs["level"] == "ERROR"
        assert "inner fail" in update_kwargs["status_message"]

    @pytest.mark.asyncio
    async def test_missing_sdk_module_does_not_block(self) -> None:
        # Force ImportError by inserting a sentinel that fails import.
        sys.modules["langfuse"] = None  # type: ignore[assignment]
        inner = _make_inner("ok")
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )
        result = await wrapper.complete([Message(content="hi")])
        assert result.text == "ok"


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_inner_and_flush(self) -> None:
        _, langfuse_cls, _ = _install_fake_langfuse_module()
        inner = _make_inner()
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )
        # Trigger lazy init by making a call first.
        await wrapper.complete([Message(content="hi")])
        await wrapper.close()
        inner.close.assert_awaited_once()
        langfuse_cls.return_value.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_swallows_flush_errors(self) -> None:
        _install_fake_langfuse_module(raise_on_flush=True)
        inner = _make_inner()
        wrapper = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
        )
        await wrapper.complete([Message(content="hi")])
        # Must not raise even though flush blows up.
        await wrapper.close()
        inner.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_works_when_inner_has_no_close(self) -> None:
        # Some LLMClients may not implement close() — Protocol doesn't require it.
        inner = SimpleNamespace(complete=AsyncMock(return_value=_fake_response()))
        wrapper = LangfuseTracedLLM(
            inner=inner,  # type: ignore[arg-type]
            config=LangfuseConfig(enabled=False),
        )
        await wrapper.close()  # should not raise


class TestLibraryTag:
    @pytest.mark.asyncio
    async def test_with_library_tag_adds_tag_without_mutating_parent(self) -> None:
        _install_fake_langfuse_module()
        inner = _make_inner()
        parent = LangfuseTracedLLM(
            inner=inner,
            config=LangfuseConfig(enabled=True),
            default_tags=["base"],
        )

        async with with_library_tag(wrapper=parent, library_id="rag-agent") as scoped:
            await scoped.complete([Message(content="x")])

        # The parent's tags are untouched (immutability).
        assert parent._default_tags == ("base",)
        # The scoped wrapper sent the merged tags.
        client = sys.modules["langfuse"].Langfuse.return_value  # type: ignore[attr-defined]
        start_kwargs = client.start_observation.call_args.kwargs
        assert "library_id:rag-agent" in start_kwargs["metadata"]["tags"]
        assert "base" in start_kwargs["metadata"]["tags"]
