"""L5: Task orchestration — QA, review, reasoning, hypothesis generation."""

from packages.orchestration.activity import (
    ActivityEvent,
    ActivityLogger,
    ActivityType,
)
from packages.orchestration.cost import (
    CostCapEnforcer,
    CostCheckResult,
    LibraryDailyCost,
)
from packages.orchestration.eval_models import (
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AnswerFeedback,
    EvalAlert,
    EvalKPIs,
    EvalSet,
    EvalSnapshot,
    Metric,
    StrategyReport,
)
from packages.orchestration.eval_protocols import (
    AlertEngine,
    EvalSnapshotter,
    FeedbackStore,
    VARComputer,
)
from packages.orchestration.library_config import (
    EmbedderSpec,
    LibraryConfig,
    LibraryConfigPatch,
    LibraryConfigStore,
    LLMRouterSpec,
    RerankerSpec,
)
from packages.orchestration.library_status import (
    LibraryStatusChecker,
    LibraryStatusEvaluation,
)
from packages.orchestration.notifications import (
    Notification,
    NotificationId,
    NotificationStore,
    NotificationType,
    Severity,
)
from packages.orchestration.protocols import (
    AnsweredQuery,
    Citation,
    CrossPaperReasoningResult,
    Hypothesis,
    HypothesisResult,
    ReasoningPath,
    ReasoningStep,
    ReviewResult,
    ReviewSection,
    TaskBudget,
    TaskCost,
    TaskRunner,
    TokenUsage,
)
from packages.orchestration.queue import (
    BudgetSpec,
    TaskBudgetRef,
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskHandle,
    TaskId,
    TaskQueue,
    TaskSpec,
    TaskState,
    TaskType,
)
from packages.orchestration.search import (
    SearchHit,
    SearchQuery,
    SearchService,
    SearchType,
)
from packages.orchestration.tasks.hypothesis_task import (
    HypothesisTask,
    HypothesisTaskConfig,
)
from packages.orchestration.tasks.qa_task import QATask
from packages.orchestration.tasks.reasoning_task import (
    CrossPaperReasoningTask,
    CrossPaperReasoningTaskConfig,
)
from packages.orchestration.tasks.review_task import (
    ReviewGenerationTask,
    ReviewGenerationTaskConfig,
)

__all__ = [
    # M7 — activity log (ADR-0014)
    "ActivityEvent",
    "ActivityLogger",
    "ActivityType",
    # M7 — eval (ADR-0016 / 0021)
    "AlertEngine",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "AnswerFeedback",
    # Existing (M1-M6)
    "AnsweredQuery",
    # M7 — task queue (ADR-0009 / 0010)
    "BudgetSpec",
    "Citation",
    # M7 — daily cost cap (ADR-0015)
    "CostCapEnforcer",
    "CostCheckResult",
    "CrossPaperReasoningResult",
    "CrossPaperReasoningTask",
    "CrossPaperReasoningTaskConfig",
    # M7 — per-library config (ADR-0012)
    "EmbedderSpec",
    "EvalAlert",
    "EvalKPIs",
    "EvalSet",
    "EvalSnapshot",
    "EvalSnapshotter",
    "FeedbackStore",
    "Hypothesis",
    "HypothesisResult",
    "HypothesisTask",
    "HypothesisTaskConfig",
    "LLMRouterSpec",
    "LibraryConfig",
    "LibraryConfigPatch",
    "LibraryConfigStore",
    "LibraryDailyCost",
    # M7 — library status (ADR-0013)
    "LibraryStatusChecker",
    "LibraryStatusEvaluation",
    "Metric",
    # M7 — notifications (ADR-0011)
    "Notification",
    "NotificationId",
    "NotificationStore",
    "NotificationType",
    "QATask",
    "ReasoningPath",
    "ReasoningStep",
    "RerankerSpec",
    "ReviewGenerationTask",
    "ReviewGenerationTaskConfig",
    "ReviewResult",
    "ReviewSection",
    # M7 — search (ADR-0023)
    "SearchHit",
    "SearchQuery",
    "SearchService",
    "SearchType",
    "Severity",
    "StrategyReport",
    "TaskBudget",
    "TaskBudgetRef",
    "TaskCost",
    "TaskEvent",
    "TaskEventBus",
    "TaskEventType",
    "TaskHandle",
    "TaskId",
    "TaskQueue",
    "TaskRunner",
    "TaskSpec",
    "TaskState",
    "TaskType",
    "TokenUsage",
    "VARComputer",
]
