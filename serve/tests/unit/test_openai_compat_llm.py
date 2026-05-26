"""Tests for OpenAICompatLLM — chat completions adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from packages.llm.adapters.openai_compat import (
    OpenAICompatLLM,
    OpenAICompatLLMConfig,
)
from packages.llm.protocols import Message


def _fake_response(text: str = "answer") -> httpx.Response:
    body = {
        "id": "chatcmpl-1",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return httpx.Response(200, json=body, request=httpx.Request("POST", "/chat/completions"))


class TestOpenAICompatLLM:
    def test_default_config(self) -> None:
        config = OpenAICompatLLMConfig()
        assert config.api_base == "https://api.openai.com/v1"
        assert config.model == "gpt-4o-mini"

    def test_headers_with_api_key(self) -> None:
        headers = OpenAICompatLLM._build_headers("sk-test")
        assert headers["Authorization"] == "Bearer sk-test"

    def test_headers_without_api_key(self) -> None:
        headers = OpenAICompatLLM._build_headers("")
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_complete_returns_text_and_usage(self) -> None:
        config = OpenAICompatLLMConfig(model="m")
        llm = OpenAICompatLLM(config)
        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(return_value=_fake_response("the answer"))

        result = await llm.complete([Message(role="user", content="hi")])

        assert result.text == "the answer"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.model == "test-model"

    @pytest.mark.asyncio
    async def test_complete_passes_temperature_and_max_tokens(self) -> None:
        config = OpenAICompatLLMConfig(model="m")
        llm = OpenAICompatLLM(config)
        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(return_value=_fake_response())

        await llm.complete(
            [Message(content="hi")],
            temperature=0.5,
            max_tokens=100,
        )

        call_kwargs = llm._client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 100
        assert payload["model"] == "m"

    @pytest.mark.asyncio
    async def test_complete_overrides_model_per_request(self) -> None:
        config = OpenAICompatLLMConfig(model="default-model")
        llm = OpenAICompatLLM(config)
        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(return_value=_fake_response())

        await llm.complete([Message(content="hi")], model="other-model")
        payload = llm._client.post.call_args.kwargs["json"]
        assert payload["model"] == "other-model"

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        llm = OpenAICompatLLM(OpenAICompatLLMConfig())
        llm._client = AsyncMock(spec=httpx.AsyncClient)
        await llm.close()
        llm._client.aclose.assert_called_once()
