"""OpenAI-compatible chat completions adapter.

Works with any provider exposing /v1/chat/completions:
OpenAI, DeepSeek, SiliconFlow, vLLM, LiteLLM, Ollama, etc.

Includes automatic retry on transient HTTP failures (timeouts,
connection drops, 5xx, 429). User-facing errors (4xx) are NOT retried.
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict

from packages.llm._retry import make_retrying
from packages.llm.protocols import LLMResponse, Message
from packages.observability import (
    LLM_COST_USD_TOTAL,
    LLM_DURATION_SECONDS,
    LLM_ERRORS_TOTAL,
    LLM_TOKENS_TOTAL,
)


class _ChoiceMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str | None = None


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: _ChoiceMessage


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    choices: list[_Choice]
    usage: _Usage = _Usage()
    model: str = ""


@dataclass(frozen=True, slots=True)
class OpenAICompatLLMConfig:
    """Configuration for the OpenAI-compatible LLM adapter."""

    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_s: int = 60
    max_attempts: int = 3
    retry_initial_wait_s: float = 2.0


class OpenAICompatLLM:
    """LLM client that calls /v1/chat/completions on any compatible endpoint."""

    def __init__(self, config: OpenAICompatLLMConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base.rstrip("/"),
            headers=self._build_headers(config.api_key),
            timeout=httpx.Timeout(config.timeout_s),
        )

    @staticmethod
    def _build_headers(api_key: str) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        effective_model = model or self._config.model
        payload: dict[str, object] = {
            "model": effective_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        retrying = make_retrying(
            max_attempts=self._config.max_attempts,
            initial_wait=self._config.retry_initial_wait_s,
        )
        response: httpx.Response | None = None
        started = _time.perf_counter()
        try:
            async for attempt in retrying:
                with attempt:
                    response = await self._client.post(
                        "/chat/completions",
                        json=payload,
                        timeout=httpx.Timeout(timeout_s),
                    )
                    response.raise_for_status()
        except Exception as exc:
            LLM_ERRORS_TOTAL.labels(
                model=effective_model, library_id="", error_type=type(exc).__name__
            ).inc()
            raise
        finally:
            LLM_DURATION_SECONDS.labels(model=effective_model, library_id="").observe(
                _time.perf_counter() - started
            )

        if response is None:
            msg = "LLM call returned no response after retries"
            raise RuntimeError(msg)

        parsed = _ChatResponse.model_validate(response.json())
        text = parsed.choices[0].message.content or "" if parsed.choices else ""
        LLM_TOKENS_TOTAL.labels(model=effective_model, kind="input", library_id="").inc(
            parsed.usage.prompt_tokens
        )
        LLM_TOKENS_TOTAL.labels(model=effective_model, kind="output", library_id="").inc(
            parsed.usage.completion_tokens
        )
        LLM_COST_USD_TOTAL.labels(model=effective_model, library_id="").inc(0.0)
        return LLMResponse(
            text=text,
            model=parsed.model or payload["model"],  # type: ignore[arg-type]
            input_tokens=parsed.usage.prompt_tokens,
            output_tokens=parsed.usage.completion_tokens,
            cost_usd=0.0,
        )

    async def close(self) -> None:
        await self._client.aclose()
