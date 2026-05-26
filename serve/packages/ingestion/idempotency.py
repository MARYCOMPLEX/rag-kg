"""Pure helpers for content-addressed ingest dedup."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 20  # 1 MiB


def hash_file(path: Path, *, chunk_size: int = _CHUNK) -> str:
    """Return the hex SHA-256 of `path`."""
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            buf = fp.read(chunk_size)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def short_hash(sha256: str, length: int = 12) -> str:
    return sha256[:length]
