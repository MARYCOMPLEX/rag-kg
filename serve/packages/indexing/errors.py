"""Indexing-domain exception hierarchy.

Per CODING_STANDARDS §8.1: each package owns its error subtree. The
fallback-chain reranker (ADR-0018 §4) needs distinct error classes so
``FallbackReranker`` can route on the cause; we do not want to map
unrelated network exceptions back to ``RerankerTimeout`` and silently
short-circuit the chain.
"""

from __future__ import annotations


class IndexingError(Exception):
    """Base for indexing-package errors."""


class RerankerError(IndexingError):
    """Base for any reranker-related failure."""


class RerankerNotAvailableError(RerankerError):
    """The reranker model / endpoint cannot be loaded or reached.

    Used by:
    - ``BGERerankerV2Adapter`` when ``sentence-transformers`` import fails
      or the model download is impossible.
    - ``CohereRerankAdapter`` when ``COHERE_API_KEY`` is absent.

    Triggers fallback-chain advance (ADR-0018 §4).
    """


class RerankerTimeoutError(RerankerError):
    """The reranker forward pass exceeded ``timeout_ms``.

    Triggers fallback-chain advance (ADR-0018 §4). Distinct from
    ``RerankerNotAvailableError`` so callers can distinguish "model is
    just slow" from "model is gone".
    """
