"""Event bus protocol definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from packages.core.models import DomainEvent

type EventHandler = Callable[[DomainEvent], Awaitable[None]]


@runtime_checkable
class EventBus(Protocol):
    """Publish-subscribe bus for domain events."""

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register a handler for a topic."""
        ...

    async def publish(self, topic: str, event: DomainEvent) -> None:
        """Publish an event to all handlers subscribed to the topic."""
        ...
