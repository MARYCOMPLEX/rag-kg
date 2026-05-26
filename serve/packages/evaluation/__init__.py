"""Evaluation subsystem — terminal package, never imported by other packages."""

from packages.evaluation.loader import FilesystemSampleLoader
from packages.evaluation.metrics.deterministic import (
    CitationPresentMetric,
    KeyPointCoverageMetric,
    LatencyConfig,
    LatencyMetric,
    MustNotContainMetric,
    RecallAtKMetric,
)
from packages.evaluation.metrics.llm_judge import (
    AnswerRelevancyConfig,
    AnswerRelevancyMetric,
    CitationF1Config,
    CitationF1Metric,
    FaithfulnessConfig,
    FaithfulnessMetric,
)
from packages.evaluation.protocols import (
    EvalRun,
    EvalRunner,
    EvalSample,
    Metric,
    MetricScore,
    RunSummary,
    SampleLoader,
    SampleResult,
)
from packages.evaluation.reporter import MarkdownReporter
from packages.evaluation.runner import DefaultEvalRunner, EvalRunnerConfig
from packages.evaluation.runs_store import JSONFileRunsStore

__all__ = [
    "AnswerRelevancyConfig",
    "AnswerRelevancyMetric",
    "CitationF1Config",
    "CitationF1Metric",
    "CitationPresentMetric",
    "DefaultEvalRunner",
    "EvalRun",
    "EvalRunner",
    "EvalRunnerConfig",
    "EvalSample",
    "FaithfulnessConfig",
    "FaithfulnessMetric",
    "FilesystemSampleLoader",
    "JSONFileRunsStore",
    "KeyPointCoverageMetric",
    "LatencyConfig",
    "LatencyMetric",
    "MarkdownReporter",
    "Metric",
    "MetricScore",
    "MustNotContainMetric",
    "RecallAtKMetric",
    "RunSummary",
    "SampleLoader",
    "SampleResult",
]
