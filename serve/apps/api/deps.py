"""FastAPI dependency injection — single shared AppContainer per process."""

from __future__ import annotations

from functools import lru_cache

from apps._shared.factories import AppContainer, build_container


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """Return the process-wide DI container (singleton)."""
    return build_container()
