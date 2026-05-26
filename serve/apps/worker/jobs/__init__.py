"""Arq job functions registered with the worker.

Each module exports an `async def run(ctx, ...) -> object` coroutine that
the Arq `WorkerSettings.functions` list references. New job modules added
in M7 are placeholders; their concrete bodies land in dedicated agent
patches per BACKEND_ROADMAP §2.1.

The naming convention is `run_<task_type>` so the queue can map
`TaskSpec.task_type` to the worker function via simple string lookup.
"""

from __future__ import annotations

# Placeholder import surface — the M7 sister agents add their own modules
# (ingest_document, extract_kg, rebuild_community, run_review, ...).
# This file exists so `apps.worker.main` can `from apps.worker.jobs import _registry`
# without a runtime ImportError when only some jobs have landed.
from apps.worker.jobs import base as base  # re-export shared helpers

__all__ = ["base"]
