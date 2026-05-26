"""LLM client protocol definitions.

LLM is a stateless compute service — no library_id needed.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """A single message in a conversation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["system", "user", "assistant"] = "user"
    content: str


class LLMResponse(BaseModel):
    """Response from an LLM completion call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = Field(default=0.0, ge=0.0)


@runtime_checkable
class LLMClient(Protocol):
    """Unified LLM completion interface."""

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse: ...
