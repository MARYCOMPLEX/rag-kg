"""Domain exceptions for the orchestration package.

Every error raised inside `packages/orchestration/**` derives from
`OrchestrationError` so the API layer can map them to HTTP status codes
in `apps/api/middleware/error_handler.py` (M7 envelope, ADR-0007).
"""

from __future__ import annotations

from packages.core.errors import RKBError


class OrchestrationError(RKBError):
    """Base for all errors raised inside L5 orchestration code."""


class QueueFullError(OrchestrationError):
    """The async queue rejected an enqueue because it is at capacity."""


class TaskNotFoundError(OrchestrationError):
    """No task with the given (library_id, task_id) tuple exists."""

    def __init__(self, library_id: str, task_id: str) -> None:
        super().__init__(f"Task not found: library_id={library_id!r} task_id={task_id!r}")
        self.library_id = library_id
        self.task_id = task_id


class TaskCancelledError(OrchestrationError):
    """A running job observed a cooperative-cancel signal."""

    def __init__(self, library_id: str, task_id: str, reason: str = "user_cancel") -> None:
        super().__init__(
            f"Task cancelled: library_id={library_id!r} task_id={task_id!r} reason={reason!r}"
        )
        self.library_id = library_id
        self.task_id = task_id
        self.reason = reason


class TaskHistoryExpiredError(OrchestrationError):
    """The Redis Stream history has been TTL'd; client must fall back to snapshot."""

    def __init__(self, library_id: str, task_id: str) -> None:
        super().__init__(f"Task history expired: library_id={library_id!r} task_id={task_id!r}")
        self.library_id = library_id
        self.task_id = task_id


class NotificationStoreError(OrchestrationError):
    """Notification persistence or LISTEN/NOTIFY failed."""


class ActivityLogError(OrchestrationError):
    """Activity log write or query failed."""


class LibraryConfigStoreError(OrchestrationError):
    """Per-library config persistence failed."""


class CostCapBlockedError(OrchestrationError):
    """LLM call refused — daily cost cap reached.

    Mapped to HTTP 402 by the API error handler (ADR-0015 §9).
    """

    def __init__(self, library_id: str, today_cost_usd: str, cap_usd: str) -> None:
        super().__init__(
            f"Daily cost cap reached: library_id={library_id!r} "
            f"spent={today_cost_usd} cap={cap_usd}"
        )
        self.library_id = library_id
        self.today_cost_usd = today_cost_usd
        self.cap_usd = cap_usd


class LibraryStatusEvaluationError(OrchestrationError):
    """Library status evaluation pass failed."""
