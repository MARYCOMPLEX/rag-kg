"""LLM gateway — unified interface for all LLM providers."""

from packages.llm.adapters.openai_compat import OpenAICompatLLM, OpenAICompatLLMConfig
from packages.llm.protocols import LLMClient, LLMResponse, Message

__all__ = [
    "LLMClient",
    "LLMResponse",
    "Message",
    "OpenAICompatLLM",
    "OpenAICompatLLMConfig",
]
