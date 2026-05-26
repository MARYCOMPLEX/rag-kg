"""Langfuse-traced wrapper for any `LLMClient`.

The wrapper is designed to be a drop-in replacement for any
`packages.llm.protocols.LLMClient` implementation. When tracing is
disabled it is a thin pass-through with zero Langfuse references touched.

When enabled, every `complete()` call is recorded as a Langfuse
generation observation. Failures in Langfuse (network, auth, init)
must NEVER block the underlying LLM call — they are logged via
structlog and swallowed.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import AsyncGenerator

    from packages.llm.protocols import LLMClient, LLMResponse, Message

logger = structlog.get_logger(__name__)

_MS_PER_SECOND = 1000.0


@dataclass(frozen=True, slots=True)
class LangfuseConfig:
    """Configuration for the Langfuse-traced LLM wrapper."""

    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "http://localhost:3000"
    flush_at: int = 10
    flush_interval_s: float = 5.0


def _serialize_messages(messages: list[Message]) -> list[dict[str, str]]:
    """Convert Pydantic Message list to plain dicts for Langfuse input."""
    return [{"role": m.role, "content": m.content} for m in messages]


class LangfuseTracedLLM:
    """Wraps an `LLMClient` and records every call as a Langfuse generation.

    Structurally satisfies the `LLMClient` Protocol so it can replace any
    underlying adapter (e.g. `OpenAICompatLLM`) without code changes elsewhere.
    """

    def __init__(
        self,
        *,
        inner: LLMClient,
        config: LangfuseConfig,
        default_tags: list[str] | None = None,
    ) -> None:
        self._inner = inner
        self._config = config
        # Defensive copy — never store caller's list reference (immutability).
        self._default_tags: tuple[str, ...] = tuple(default_tags or [])
        # Lazy: only touch the SDK when enabled.
        self._client: Any | None = None

    def _get_client(self) -> Any | None:
        """Return a Langfuse client, lazily initialized.

        Returns `None` if disabled or if init fails — caller must handle.
        """
        if not self._config.enabled:
            return None
        if self._client is not None:
            return self._client
        try:
            from langfuse import Langfuse  # noqa: PLC0415 — lazy import by design
        except ImportError as exc:
            logger.warning("langfuse_sdk_import_failed", error=str(exc))
            return None
        try:
            self._client = Langfuse(
                public_key=self._config.public_key,
                secret_key=self._config.secret_key,
                host=self._config.host,
                flush_at=self._config.flush_at,
                flush_interval=self._config.flush_interval_s,
            )
        except Exception as exc:
            logger.warning("langfuse_init_failed", error=str(exc))
            return None
        return self._client

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse:
        # Fast path: disabled — no SDK touched, no overhead.
        if not self._config.enabled:
            return await self._inner.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )

        client = self._get_client()
        # If client init failed, still call the inner LLM — never block.
        if client is None:
            return await self._inner.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )

        generation = self._safe_start_generation(
            client=client,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        start = time.perf_counter()
        try:
            response = await self._inner.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * _MS_PER_SECOND
            self._safe_end_generation(
                generation=generation,
                response=None,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise

        latency_ms = (time.perf_counter() - start) * _MS_PER_SECOND
        self._safe_end_generation(
            generation=generation,
            response=response,
            latency_ms=latency_ms,
            error=None,
        )
        return response

    def _safe_start_generation(
        self,
        *,
        client: Any,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Any | None:
        """Start a generation; never raise."""
        metadata: dict[str, Any] = {"tags": list(self._default_tags)}
        try:
            return client.start_observation(
                name="llm.complete",
                as_type="generation",
                input=_serialize_messages(messages),
                model=model or "",
                model_parameters={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("langfuse_start_generation_failed", error=str(exc))
            return None

    def _safe_end_generation(
        self,
        *,
        generation: Any | None,
        response: LLMResponse | None,
        latency_ms: float,
        error: str | None,
    ) -> None:
        """Record output + usage and end the generation; never raise."""
        if generation is None:
            return
        try:
            update_kwargs: dict[str, Any] = {
                "metadata": {
                    "tags": list(self._default_tags),
                    "latency_ms": latency_ms,
                },
            }
            if response is not None:
                update_kwargs["output"] = response.text
                update_kwargs["model"] = response.model
                update_kwargs["usage_details"] = {
                    "input": response.input_tokens,
                    "output": response.output_tokens,
                }
            if error is not None:
                update_kwargs["level"] = "ERROR"
                update_kwargs["status_message"] = error
            generation.update(**update_kwargs)
            generation.end()
        except Exception as exc:
            logger.warning("langfuse_end_generation_failed", error=str(exc))

    def child_with_tag(self, tag: str) -> LangfuseTracedLLM:
        """Return a sibling wrapper with `tag` appended to default tags.

        The sibling shares this wrapper's inner LLM client and any
        already-initialized Langfuse client, so no double-init or
        double-flush occurs. The original is left unchanged (immutability).
        """
        merged_tags = [*self._default_tags, tag]
        sibling = LangfuseTracedLLM(
            inner=self._inner,
            config=self._config,
            default_tags=merged_tags,
        )
        # Share the lazily-initialized client to avoid double init/flush.
        sibling._client = self._client
        return sibling

    def adopt_child_client(self, child: LangfuseTracedLLM) -> None:
        """Adopt the lazily-initialized Langfuse client of a sibling.

        Used when a child wrapper triggered SDK init but the parent did
        not — ensures the parent's `close()` still flushes pending events.
        """
        if self._client is None and child._client is not None:
            self._client = child._client

    async def close(self) -> None:
        """Close the inner client and flush any pending Langfuse events."""
        # Always close the underlying client first — its resources matter most.
        try:
            inner_close = getattr(self._inner, "close", None)
            if inner_close is not None:
                await inner_close()
        finally:
            if self._client is not None:
                try:
                    self._client.flush()
                except Exception as exc:
                    logger.warning("langfuse_flush_failed", error=str(exc))


@asynccontextmanager
async def with_library_tag(
    *,
    wrapper: LangfuseTracedLLM,
    library_id: str,
) -> AsyncGenerator[LangfuseTracedLLM, None]:
    """Yield a sibling wrapper with `library_id:<id>` added to default tags.

    The original wrapper is left untouched (immutability). The yielded
    instance shares the same inner client and Langfuse client (lazy init
    is preserved on the original). It is the caller's responsibility not
    to call `close()` on the yielded sibling — close the original.
    """
    sibling = wrapper.child_with_tag(f"library_id:{library_id}")
    try:
        yield sibling
    finally:
        # If the sibling lazily initialized a client, hand it back so the
        # parent's close() flushes the pending events.
        wrapper.adopt_child_client(sibling)


def update_config(
    config: LangfuseConfig,
    **changes: Any,
) -> LangfuseConfig:
    """Return a new `LangfuseConfig` with the given fields replaced.

    Convenience helper for callers; preserves immutability.
    """
    return replace(config, **changes)
