"""Per-request sandbox directory helper for ZIP/folder uploads (ADR-0019 §3).

A sandbox is `<root>/<library_id>/<request_id>/` and contains:

- `inbox/` — raw multipart payload (the ZIP, or the multi-file dump)
- `extracted/` — extracted contents, never directly mounted by the worker
- `staging/` — validated PDFs ready for the worker to consume

The sandbox is always cleaned up in `__aexit__` (success or failure). The
worker startup hook should also call `purge_orphans(root, max_age_s=3600)`
to sweep abandoned directories from a previous crash.

Library-id and request-id slug validation happens at construction time;
nothing else in this module trusts the inputs.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Self

# Tight slug pattern — the same shape we use for library_id elsewhere.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _validate_slug(value: str, *, kind: str) -> str:
    """Return `value` if it matches the slug pattern, else raise ValueError."""
    if not _SLUG_RE.match(value):
        msg = f"invalid {kind}: {value!r}"
        raise ValueError(msg)
    return value


class SandboxDirectory:
    """A per-request sandbox rooted at `<root>/<library_id>/<request_id>/`.

    Use as an async context manager. Sub-directories `inbox`, `extracted`,
    and `staging` are created on enter and removed on exit (recursively).

    Example:
        async with SandboxDirectory.create(root, library_id, request_id) as box:
            # box.inbox / box.extracted / box.staging are guaranteed to exist
            ...
        # everything under `box.path` is gone at this point
    """

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        # Private constructor — callers should use `create()` so the path
        # is stamped with the slug-validated parts.
        self._path = path

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        root: Path,
        library_id: str,
        request_id: str,
    ) -> SandboxDirectory:
        """Materialize the sandbox tree on disk.

        Both `library_id` and `request_id` are slug-validated; anything that
        doesn't match is rejected before we touch the filesystem.
        """
        _validate_slug(library_id, kind="library_id")
        _validate_slug(request_id, kind="request_id")
        target = root / library_id / request_id
        target.mkdir(parents=True, exist_ok=False)
        for sub in ("inbox", "extracted", "staging"):
            (target / sub).mkdir(parents=True, exist_ok=True)
        return cls(target)

    @classmethod
    def from_tempdir(cls, library_id: str, request_id: str) -> SandboxDirectory:
        """Convenience for unit tests — uses `tempfile.mkdtemp()` as root."""
        root = Path(tempfile.mkdtemp(prefix="rkb-sandbox-"))
        return cls.create(root, library_id, request_id)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Absolute (resolved) sandbox root."""
        return self._path

    @property
    def inbox(self) -> Path:
        return self._path / "inbox"

    @property
    def extracted(self) -> Path:
        return self._path / "extracted"

    @property
    def staging(self) -> Path:
        return self._path / "staging"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Remove the sandbox tree. Idempotent and best-effort."""
        if self._path.exists():
            shutil.rmtree(self._path, ignore_errors=True)


def purge_orphans(root: Path, *, max_age_s: int = 3600) -> int:
    """Sweep sandbox directories older than `max_age_s` seconds.

    Returns the number of directories removed. Used by the worker startup
    hook to clean up after a crash. Best-effort; errors are swallowed
    because this is a maintenance helper, not user-facing logic.
    """
    if not root.exists():
        return 0

    import time

    cutoff = time.time() - max_age_s
    removed = 0
    for lib_dir in root.iterdir():
        if not lib_dir.is_dir():
            continue
        for req_dir in lib_dir.iterdir():
            if not req_dir.is_dir():
                continue
            try:
                mtime = req_dir.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                shutil.rmtree(req_dir, ignore_errors=True)
                removed += 1
    return removed


__all__ = ["SandboxDirectory", "purge_orphans"]
