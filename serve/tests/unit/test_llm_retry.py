"""Tests for LLM retry policy on transient HTTP failures."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from packages.llm._retry import _is_transient, make_retrying
from packages.llm.adapters.openai_compat import (
    OpenAICompatLLM,
    OpenAICompatLLMConfig,
)
from packages.llm.protocols import Message


def _ok_response(text: str = "ok") -> httpx.Response:
    body = {
        "id": "x",
        "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    return httpx.Response(200, json=body, request=httpx.Request("POST", "/x"))


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "/x")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


class TestIsTransient:
    def test_read_timeout_is_transient(self) -> None:
        assert _is_transient(httpx.ReadTimeout("slow")) is True

    def test_connect_error_is_transient(self) -> None:
        assert _is_transient(httpx.ConnectError("nope")) is True

    def test_remote_protocol_error_is_transient(self) -> None:
        assert _is_transient(httpx.RemoteProtocolError("disconnected")) is True

    def test_500_is_transient(self) -> None:
        assert _is_transient(_http_status_error(500)) is True

    def test_503_is_transient(self) -> None:
        assert _is_transient(_http_status_error(503)) is True

    def test_429_is_transient(self) -> None:
        assert _is_transient(_http_status_error(429)) is True

    def test_400_is_not_transient(self) -> None:
        assert _is_transient(_http_status_error(400)) is False

    def test_401_is_not_transient(self) -> None:
        assert _is_transient(_http_status_error(401)) is False

    def test_404_is_not_transient(self) -> None:
        assert _is_transient(_http_status_error(404)) is False

    def test_value_error_is_not_transient(self) -> None:
        assert _is_transient(ValueError("nope")) is False


class TestMakeRetrying:
    def test_returns_async_retrying_instance(self) -> None:
        retry = make_retrying(max_attempts=3)
        assert retry is not None


class TestRetryIntegration:
    @pytest.mark.asyncio
    async def test_succeeds_after_one_timeout(self) -> None:
        config = OpenAICompatLLMConfig(model="m", max_attempts=3, retry_initial_wait_s=0.01)
        llm = OpenAICompatLLM(config)

        # First call raises ReadTimeout, second succeeds
        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(
            side_effect=[httpx.ReadTimeout("slow"), _ok_response("recovered")]
        )

        result = await llm.complete([Message(content="hi")])
        assert result.text == "recovered"
        assert llm._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_gives_up_after_max_attempts(self) -> None:
        config = OpenAICompatLLMConfig(model="m", max_attempts=2, retry_initial_wait_s=0.01)
        llm = OpenAICompatLLM(config)

        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(side_effect=httpx.ReadTimeout("slow"))

        with pytest.raises(httpx.ReadTimeout):
            await llm.complete([Message(content="hi")])
        assert llm._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_4xx(self) -> None:
        config = OpenAICompatLLMConfig(model="m", max_attempts=3, retry_initial_wait_s=0.01)
        llm = OpenAICompatLLM(config)

        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(side_effect=_http_status_error(400))

        with pytest.raises(httpx.HTTPStatusError):
            await llm.complete([Message(content="hi")])
        # No retry for 400
        assert llm._client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_5xx_then_succeeds(self) -> None:
        config = OpenAICompatLLMConfig(model="m", max_attempts=3, retry_initial_wait_s=0.01)
        llm = OpenAICompatLLM(config)

        llm._client = AsyncMock(spec=httpx.AsyncClient)
        llm._client.post = AsyncMock(side_effect=[_http_status_error(503), _ok_response("ok")])

        result = await llm.complete([Message(content="hi")])
        assert result.text == "ok"
        assert llm._client.post.call_count == 2
