"""Append-only JSONL store for eval run summaries.

Each line is a serialized `RunSummary` JSON object. Stored under
`data/libraries/<library_id>/evals/runs/eval_runs.jsonl`. The store is
intentionally minimal: append on save, scan-tail on read. Heavy queries
should use a dedicated metrics warehouse, not this file.
"""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
from typing import Final

from packages.evaluation.protocols import EvalRun, RunSummary

_DEFAULT_DATA_DIR: Final[Path] = Path("data")
_LIBRARIES_SUBDIR: Final[str] = "libraries"
_EVALS_SUBDIR: Final[str] = "evals"
_RUNS_SUBDIR: Final[str] = "runs"
_RUNS_FILE: Final[str] = "eval_runs.jsonl"


class JSONFileRunsStore:
    """Filesystem-backed JSONL store for `RunSummary` records."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir if data_dir is not None else _DEFAULT_DATA_DIR

    async def save(self, run: EvalRun) -> Path:
        path = self._runs_path(run.summary.library_id)
        await asyncio.to_thread(self._append_line_sync, path, run.summary)
        return path

    async def list_recent(self, library_id: str, limit: int = 10) -> list[RunSummary]:
        if limit <= 0:
            return []
        path = self._runs_path(library_id)
        if not path.exists():
            return []
        return await asyncio.to_thread(self._tail_sync, path, limit)

    # --- internals ---------------------------------------------------------

    def _runs_path(self, library_id: str) -> Path:
        return (
            self._data_dir
            / _LIBRARIES_SUBDIR
            / library_id
            / _EVALS_SUBDIR
            / _RUNS_SUBDIR
            / _RUNS_FILE
        )

    @staticmethod
    def _append_line_sync(path: Path, summary: RunSummary) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = summary.model_dump_json()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    @staticmethod
    def _tail_sync(path: Path, limit: int) -> list[RunSummary]:
        # Bounded tail: deque drops older entries as we stream the file.
        # Cheap and avoids allocating the full file in memory.
        recent: deque[str] = deque(maxlen=limit)
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                stripped = raw.strip()
                if stripped:
                    recent.append(stripped)
        return [RunSummary.model_validate_json(line) for line in recent]


__all__ = ["JSONFileRunsStore"]
