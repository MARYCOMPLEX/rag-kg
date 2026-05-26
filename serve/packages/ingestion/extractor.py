"""ZIP / folder safe extraction (ADR-0019).

Implements the manifest-then-stream extraction algorithm spelled out in
ADR-0019 §5, plus the post-extract PDF discovery step (§6). All hard
limits live in `LIMITS` (a frozen dataclass) so callers can override
per-deployment without touching code.

Safety contract:

- Reject path traversal (`..`, leading `/`) before opening any file.
- Reject symlinks (zip `external_attr` 0o120000) before write.
- Reject filename overlength and path-depth overlength.
- Streamed extraction with a per-file size cap defends against lying
  declared sizes (zip-bomb).
- Resolve every target through `Path.resolve()` and verify it stays
  inside `sandbox.resolve()`.
- Hard ceilings on total extracted bytes / file count abort the entire
  extraction.

This module is intentionally *only* a file-system tool: it does not
enqueue tasks, talk to the queue, or hash files. Hashing is downstream
in the per-document ingest job (ADR-0007 §4 reuse).
"""

from __future__ import annotations

import asyncio
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------
# Limits (ADR-0019 §4)
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExtractionLimits:
    """Hard caps on a single extraction run.

    Defaults match ADR-0019 §4. Operators can build a relaxed instance
    for the CLI batch path (per ADR-0019: "soft in CLI mode"); the HTTP
    API uses the defaults as a no-override floor.
    """

    max_zip_size_bytes: int = 500 * 1024 * 1024  # 500 MB
    max_pdf_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    max_extracted_total_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB
    max_extracted_file_count: int = 1000
    max_path_depth: int = 16
    max_filename_length: int = 255
    max_per_request_disk_quota: int = 5 * 1024 * 1024 * 1024  # 5 GB
    extraction_timeout_s: float = 120.0


LIMITS = ExtractionLimits()

# Streaming copy buffer; the size cap defends against lying headers.
_COPY_BUF = 1 << 20  # 1 MiB

#: PDF magic number — first five bytes.
_PDF_MAGIC = b"%PDF-"
_PDF_HEAD_READ = 5


# ----------------------------------------------------------------------
# Errors (mapped to RKBError envelope by the API layer; see ADR-0007)
# ----------------------------------------------------------------------


class ExtractionError(Exception):
    """Base class for extractor-domain errors."""


class ZipTooLargeError(ExtractionError):
    """ZIP payload exceeds `max_zip_size_bytes`."""


class ZipBombError(ExtractionError):
    """Total extracted bytes (or per-file cap) exceeded — likely zip-bomb."""


class TooManyFilesError(ExtractionError):
    """Manifest declared more files than `max_extracted_file_count`."""


class PathTraversalError(ExtractionError):
    """A member path tried to escape the sandbox (`..` or absolute)."""


class SymlinkRejectedError(ExtractionError):
    """A member entry was a symlink (refused — see ADR-0019 §5 line 2)."""


class ExtractionTimeoutError(ExtractionError):
    """Extraction exceeded `extraction_timeout_s` wall-clock seconds."""


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rejection:
    """One file the extractor refused, plus a machine-readable reason.

    `code` mirrors ADR-0019's error code names so the UI can render
    human-friendly text from a stable string set.
    """

    name: str
    code: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ExtractionReport:
    """Summary of a successful (possibly partial) extraction."""

    extracted_count: int
    extracted_bytes: int
    rejected: tuple[Rejection, ...] = ()
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class _ManifestEntry:
    """Validated manifest row — what we *plan* to extract."""

    info: zipfile.ZipInfo
    target: Path


@dataclass(slots=True)
class _ExtractionState:
    """Mutable accumulator for the extraction loop."""

    extracted_count: int = 0
    extracted_bytes: int = 0
    rejections: list[Rejection] = field(default_factory=list)


# ----------------------------------------------------------------------
# Public API — extract_zip
# ----------------------------------------------------------------------


async def extract_zip(
    zip_path: Path,
    sandbox_extracted: Path,
    *,
    limits: ExtractionLimits = LIMITS,
) -> ExtractionReport:
    """Extract `zip_path` into `sandbox_extracted` enforcing every limit.

    The destination directory MUST already exist (use
    `SandboxDirectory.create(...).extracted`). The function refuses to
    write outside it.

    Wall-clock timeout: `limits.extraction_timeout_s`. Hard caps in
    `limits.max_extracted_total_bytes` / `max_extracted_file_count`.

    Returns:
        An `ExtractionReport` with rejection details. Errors that abort
        the entire extraction (zip-bomb, too-many-files, path-traversal
        on the *whole* archive) raise an `ExtractionError` subclass.
    """
    if not zip_path.is_file():
        msg = f"zip path is not a file: {zip_path}"
        raise ExtractionError(msg)

    size = zip_path.stat().st_size
    if size > limits.max_zip_size_bytes:
        msg = f"zip exceeds max size: {size} > {limits.max_zip_size_bytes} bytes"
        raise ZipTooLargeError(msg)

    sandbox_root = sandbox_extracted.resolve()
    if not sandbox_root.is_dir():
        msg = f"sandbox extracted dir does not exist: {sandbox_root}"
        raise ExtractionError(msg)

    loop = asyncio.get_running_loop()
    started = loop.time()

    try:
        async with asyncio.timeout(limits.extraction_timeout_s):
            report = await asyncio.to_thread(
                _extract_zip_sync, zip_path, sandbox_root, limits, started, loop
            )
    except TimeoutError as exc:
        raise ExtractionTimeoutError(f"extraction exceeded {limits.extraction_timeout_s}s") from exc

    return report


def _extract_zip_sync(
    zip_path: Path,
    sandbox_root: Path,
    limits: ExtractionLimits,
    started: float,
    loop: asyncio.AbstractEventLoop,
) -> ExtractionReport:
    """Blocking core; runs in a worker thread under `asyncio.to_thread`.

    Splits naturally into: (1) manifest scan that aborts on global limits,
    (2) per-entry write loop that streams under a size cap.
    """
    state = _ExtractionState()

    with zipfile.ZipFile(zip_path) as zf:
        manifest = _build_manifest(zf, sandbox_root, limits, state)
        for entry in manifest:
            _stream_one_entry(zf, entry, limits, state)

    return ExtractionReport(
        extracted_count=state.extracted_count,
        extracted_bytes=state.extracted_bytes,
        rejected=tuple(state.rejections),
        duration_s=loop.time() - started,
    )


# ----------------------------------------------------------------------
# Manifest scan (pre-write validation)
# ----------------------------------------------------------------------


def _build_manifest(
    zf: zipfile.ZipFile,
    sandbox_root: Path,
    limits: ExtractionLimits,
    state: _ExtractionState,
) -> list[_ManifestEntry]:
    """Walk the ZIP manifest, dropping malicious / oversized entries.

    Mutates `state.rejections` for soft rejections; raises for the hard
    caps that should abort the whole archive.
    """
    declared_total = 0
    declared_count = 0
    accepted: list[_ManifestEntry] = []

    for info in zf.infolist():
        if info.is_dir():
            continue
        rejection = _classify_entry(info, sandbox_root, limits)
        if rejection is not None:
            state.rejections.append(rejection)
            continue

        declared_total += info.file_size
        declared_count += 1
        if declared_total > limits.max_extracted_total_bytes:
            raise ZipBombError(
                f"declared total {declared_total} exceeds {limits.max_extracted_total_bytes}"
            )
        if declared_count > limits.max_extracted_file_count:
            raise TooManyFilesError(
                f"declared {declared_count} > {limits.max_extracted_file_count}"
            )

        target = (sandbox_root / info.filename).resolve()
        accepted.append(_ManifestEntry(info=info, target=target))

    return accepted


def _classify_entry(
    info: zipfile.ZipInfo,
    sandbox_root: Path,
    limits: ExtractionLimits,
) -> Rejection | None:
    """Return a Rejection for soft-bad entries or `None` if entry passes.

    Hard-bad cases (path traversal that resolves outside the sandbox)
    are handled by the resolved-target check after this function — those
    raise instead.
    """
    raw_name = info.filename
    parts = Path(raw_name).parts

    # 1. Absolute path or `..` segment — refuse before resolving.
    if raw_name.startswith("/") or raw_name.startswith("\\"):
        return Rejection(name=raw_name, code="ZIP_PATH_TRAVERSAL", detail="absolute")
    if ".." in parts:
        return Rejection(name=raw_name, code="ZIP_PATH_TRAVERSAL", detail="dotdot")

    # 2. Symlink bit (Unix mode 0o120000 in `external_attr` high 16 bits).
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        return Rejection(name=raw_name, code="ZIP_SYMLINK")

    # 3. Path depth.
    if len(parts) > limits.max_path_depth:
        return Rejection(name=raw_name, code="ZIP_PATH_TOO_DEEP")

    # 4. File name length.
    if len(Path(raw_name).name) > limits.max_filename_length:
        return Rejection(name=raw_name, code="ZIP_NAME_TOO_LONG")

    # 5. Per-file declared size (catches obvious bombs early).
    if info.file_size > limits.max_pdf_size_bytes * 5:
        return Rejection(
            name=raw_name,
            code="ZIP_FILE_TOO_LARGE",
            detail=f"declared {info.file_size}",
        )

    # 6. Resolved target containment. Realpath both sides and verify
    #    `sandbox_root` is an ancestor of `target`.
    target = (sandbox_root / raw_name).resolve()
    if not _is_under(target, sandbox_root):
        return Rejection(
            name=raw_name,
            code="ZIP_SANDBOX_ESCAPE",
            detail=f"resolves to {target}",
        )

    return None


def _is_under(child: Path, ancestor: Path) -> bool:
    """True if `child` is `ancestor` or below it. Both paths must be resolved."""
    try:
        child.relative_to(ancestor)
    except ValueError:
        return False
    return True


# ----------------------------------------------------------------------
# Streaming extraction (post-validation)
# ----------------------------------------------------------------------


def _stream_one_entry(
    zf: zipfile.ZipFile,
    entry: _ManifestEntry,
    limits: ExtractionLimits,
    state: _ExtractionState,
) -> None:
    """Extract one validated entry, streaming with a per-file size cap.

    Updates `state.extracted_count` / `extracted_bytes`. Raises
    `ZipBombError` if a file's actual bytes exceed its per-file cap.
    """
    target = entry.target
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    cap = limits.max_pdf_size_bytes
    with zf.open(entry.info) as src, target.open("wb") as dst:
        while True:
            buf = src.read(_COPY_BUF)
            if not buf:
                break
            written += len(buf)
            if written > cap:
                # Truncate & remove the partial file so callers don't
                # see a garbage half-written PDF on disk.
                dst.close()
                target.unlink(missing_ok=True)
                raise ZipBombError(f"entry {entry.info.filename} exceeded per-file cap {cap}")
            dst.write(buf)
            state.extracted_bytes += len(buf)
            if state.extracted_bytes > limits.max_extracted_total_bytes:
                dst.close()
                target.unlink(missing_ok=True)
                raise ZipBombError(f"total bytes exceeded {limits.max_extracted_total_bytes}")

    state.extracted_count += 1


# ----------------------------------------------------------------------
# Public API — discover_pdfs / walk_folder
# ----------------------------------------------------------------------


def discover_pdfs(
    root: Path,
    *,
    limits: ExtractionLimits = LIMITS,
) -> list[Path]:
    """Return PDFs under `root`: extension + magic + size sanity check.

    See ADR-0019 §6. Non-PDFs are silently skipped — the caller is
    expected to surface `len(returned) vs len(walked)` to the user.
    """
    if not root.is_dir():
        return []

    pdfs: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".pdf":
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if not (0 < stat.st_size <= limits.max_pdf_size_bytes):
            continue
        try:
            with path.open("rb") as f:
                head = f.read(_PDF_HEAD_READ)
        except OSError:
            continue
        if head != _PDF_MAGIC:
            continue
        pdfs.append(path)
    return pdfs


def walk_folder(folder_path: Path) -> list[Path]:
    """Recursively walk `folder_path` returning every regular file.

    Symlinks are *not* followed (defense-in-depth against an attacker
    seeding the upload directory with a symlink to `/etc/passwd`).
    """
    if not folder_path.is_dir():
        return []
    out: list[Path] = []
    for path in folder_path.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            out.append(path)
    return out


# ----------------------------------------------------------------------
# Quota helpers
# ----------------------------------------------------------------------


def directory_size(root: Path) -> int:
    """Sum of file sizes under `root` (best-effort)."""
    total = 0
    if not root.is_dir():
        return 0
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def assert_within_quota(
    root: Path,
    *,
    limits: ExtractionLimits = LIMITS,
) -> None:
    """Raise `ZipBombError` if `root` exceeds the per-request disk quota."""
    used = directory_size(root)
    if used > limits.max_per_request_disk_quota:
        raise ZipBombError(f"sandbox quota exceeded: {used} > {limits.max_per_request_disk_quota}")


__all__: Iterable[str] = (
    "LIMITS",
    "ExtractionError",
    "ExtractionLimits",
    "ExtractionReport",
    "ExtractionTimeoutError",
    "PathTraversalError",
    "Rejection",
    "SymlinkRejectedError",
    "TooManyFilesError",
    "ZipBombError",
    "ZipTooLargeError",
    "assert_within_quota",
    "directory_size",
    "discover_pdfs",
    "extract_zip",
    "walk_folder",
)
