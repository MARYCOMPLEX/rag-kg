"""Filesystem-based Library metadata repository.

Stores library meta as `data/libraries/<library_id>/meta.yaml`.

Why FS over Postgres for M1: library meta is a tiny stable payload
(slug + name + description + created_at). FS is zero-setup, trivially
testable, and survives docker container resets. Migrate to Postgres in
M2 when audit log requirements emerge.
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from packages.core.errors import LibraryAlreadyExistsError, LibraryNotFoundError
from packages.core.models import LIBRARY_ID_PATTERN, Language, Library

_LIBRARY_ID_RE = re.compile(LIBRARY_ID_PATTERN)


class FilesystemLibraryRepository:
    """Library repo persisting `meta.yaml` per library directory."""

    def __init__(self, data_dir: Path) -> None:
        self._libraries_root = Path(data_dir) / "libraries"
        self._libraries_root.mkdir(parents=True, exist_ok=True)

    def _library_dir(self, library_id: str) -> Path:
        return self._libraries_root / library_id

    def _meta_path(self, library_id: str) -> Path:
        return self._library_dir(library_id) / "meta.yaml"

    async def create(self, library: Library) -> None:
        if await self.exists(library.library_id):
            raise LibraryAlreadyExistsError(library.library_id)
        lib_dir = self._library_dir(library.library_id)
        (lib_dir / "corpus" / "spike").mkdir(parents=True, exist_ok=True)
        (lib_dir / "corpus" / "full").mkdir(parents=True, exist_ok=True)
        (lib_dir / "evals").mkdir(parents=True, exist_ok=True)
        self._write_meta(library)

    async def get(self, library_id: str) -> Library | None:
        meta = self._meta_path(library_id)
        if not meta.exists():
            return None
        with meta.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        try:
            return Library.model_validate(data)
        except ValidationError as e:
            msg = f"Invalid meta.yaml for library '{library_id}': {e}"
            raise ValueError(msg) from e

    async def list_all(self) -> list[Library]:
        libraries: list[Library] = []
        if not self._libraries_root.exists():
            return libraries
        for entry in sorted(self._libraries_root.iterdir()):
            if not entry.is_dir():
                continue
            lib = await self.get(entry.name)
            if lib is not None:
                libraries.append(lib)
        return libraries

    async def delete(self, library_id: str) -> None:
        if not (await self.exists(library_id)):
            raise LibraryNotFoundError(library_id)
        shutil.rmtree(self._library_dir(library_id))

    async def exists(self, library_id: str) -> bool:
        return self._meta_path(library_id).exists()

    def _write_meta(self, library: Library) -> None:
        data = {
            "library_id": library.library_id,
            "name": library.name,
            "description": library.description,
            "created_at": library.created_at.isoformat(),
            "domain": library.domain,
            "language": library.language,
        }
        # Drop None to keep YAML clean
        data = {k: v for k, v in data.items() if v is not None}
        with self._meta_path(library.library_id).open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def make_library(
    *,
    library_id: str,
    name: str,
    description: str | None = None,
    created_at: datetime | None = None,
    language: Language | None = None,
) -> Library:
    """Validate slug + construct a Library model.

    `language` follows ADR_REVIEW R10 — `Literal["en","zh","mixed"] | None`.
    """
    if not _LIBRARY_ID_RE.match(library_id):
        msg = (
            f"Invalid library_id '{library_id}'. "
            "Must match pattern: lowercase, start with letter, 3-31 chars, "
            "only [a-z0-9-]."
        )
        raise ValueError(msg)

    return Library(
        library_id=library_id,
        name=name,
        description=description,
        created_at=created_at or datetime.now(UTC),
        language=language,
    )
