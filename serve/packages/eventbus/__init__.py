"""In-process event bus with pluggable backend.

Provides pub/sub for domain events. Kafka-ready interface
but starts with an in-memory implementation.
"""

from packages.eventbus.protocols import EventBus, EventHandler
from packages.eventbus.service import InMemoryEventBus

__all__ = [
    "EventBus",
    "EventHandler",
    "InMemoryEventBus",
]
