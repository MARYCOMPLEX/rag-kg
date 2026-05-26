# ADR-0019: ZIP / Folder Upload Pipeline and Sandboxed Extraction

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §3.6 Gap 1 (S6 Documents); PRD §8.2 (M1 ingestion) and §14.2 (M7 UX — drag-drop folder)
**Related**: ADR-0001 (modular monolith), ADR-0007 (error envelope + ingest idempotency), ADR-0009 (async task queue), ADR-0010 (SSE stage events), ADR-0011 (notification center), ADR-0015 (daily cost cap)

## Context

S6 (Documents) in the prototype lets the user drag a **PDF, a ZIP, or a
folder** onto the upload hot zone. Today the API only accepts a single PDF
multipart payload (`POST /v1/libraries/{lib}/ingest`). BACKEND_ROADMAP §3.6
Gap 1 lists the missing pieces:

- `apps/api/routes/ingest.py` must accept ZIP / multi-file multipart.
- `packages/ingestion/extractor.py` (new) must implement
  `extract_zip(path) -> list[Path]` and `walk_folder(path) -> list[Path]`.
- The worker needs an `ingest_batch` job that fans out into N
  `ingest_document` sub-tasks (ADR-0009 already provides the queue and
  sub-task plumbing).

The hard problem is not the plumbing. It is **safety**: ZIP archives are a
classic attack surface (zip-bomb, path traversal, symlink escape, decompression
fork bomb), and any path traversal here punches through `library_id`
isolation (ADR-0003) by writing to the wrong Library's directory or escaping
the sandbox altogether. We also need to bound disk and time so a 500 MB
malicious ZIP doesn't take down the worker.

A second concern is **observability and partial failure**: a 200-PDF ZIP
where 3 PDFs fail parsing must complete, return a structured report, and
keep the 197 succeeded documents indexed. The user gets one notification with
the failure count; failed PDFs are listed with retry handles (BACKEND_ROADMAP
§3.6 Gap 3 covers per-document retry).

### Forces

- **Safety > convenience.** A single CVE in our extractor poisons every
  Library on the box. Sandboxing is mandatory, not optional.
- **`library_id` propagation.** Every extracted PDF inherits the parent
  upload's `library_id`. There is no cross-Library batch (PRD §16.6).
- **Idempotency reuse.** ADR-0007 §4 already SHA-256-hashes ingest inputs
  and stores `(library_id, file_sha256)` in the ingest state table.
  Re-uploading a folder containing PDFs that already succeeded must short-
  circuit through the same path; it is **not** acceptable to re-embed.
- **Disk budget.** A 500 MB ZIP can expand to 5 GB if we let it. The worker
  box runs Postgres + Qdrant + Neo4j + OpenSearch + Redis + MinIO; spare
  disk is not abundant.
- **Frontend stays cheap.** BACKEND_ROADMAP §3.6 prototype shows the user
  drag-dropping a folder. We considered front-end ZIP unpack; rejected
  (browser ZIP libs are uneven, OOM on big folders, and we'd lose the
  server-side hash chain that ADR-0007 relies on).
- **Cost cap visibility.** A 200-PDF ZIP triggers 200 ingest jobs which
  trigger embeddings + KG extraction. ADR-0015 daily cap must be checked at
  the **batch level** (estimate before fan-out) and again **per child
  job** (because cost is realized one PDF at a time).

## Decision

We accept ZIP and folder uploads through `POST /v1/libraries/{lib}/ingest`
with a `kind=zip|folder` discriminator. The API extracts into a
**per-request sandbox directory** with a hard disk quota, walks recursively
to find PDFs (extension + magic-number check), and enqueues a single
`ingest_batch` parent job. The parent fans out into one `ingest_document`
sub-task per discovered PDF. All limits are enforced at extraction time, not
at parse time.

### 1. API surface

```
POST /v1/libraries/{lib}/ingest
Content-Type: multipart/form-data

field: file        (required, binary)
field: kind        (required, "pdf" | "zip" | "folder")
field: parser      (optional, "mineru" | "nougat" | "auto", default "auto")
field: tags        (optional, JSON array of strings)
```

`kind=folder` arrives as a **multi-file multipart** — the browser flattens
the folder; we re-discover its tree by joining `webkitRelativePath` headers
when present, falling back to flat list. `kind=zip` arrives as one payload
with `Content-Type: application/zip` (we don't trust the header but record
it for debugging).

Response (parent task handle):

```json
{
  "code": "OK",
  "data": {
    "task_id": "tsk_01HZ...",
    "library_id": "lib_x",
    "kind": "zip",
    "discovered_pdfs": 47,
    "skipped_files": 3,
    "estimated_cost_usd": "1.84"
  }
}
```

Error envelope follows ADR-0007.

### 2. `BatchIngestor` Protocol contract

The Protocol lives in `packages/ingestion/batch_ingestor.py` (per
BACKEND_ROADMAP §3.6 Gap 1). Two methods, both Library-scoped (PRD §16.6).

```python
# packages/ingestion/batch_ingestor.py
from pathlib import Path
from typing import Protocol

from packages.core.models import TaskHandle


class BatchIngestor(Protocol):
    async def ingest_zip(
        self,
        library_id: str,
        zip_path: Path,
        *,
        parser: str = "auto",
        tags: list[str] | None = None,
    ) -> TaskHandle: ...

    async def ingest_folder(
        self,
        library_id: str,
        folder_path: Path,
        *,
        parser: str = "auto",
        tags: list[str] | None = None,
    ) -> TaskHandle: ...
```

Returned `TaskHandle` points at the **parent** `ingest_batch` task. The
worker writes child task IDs into `TaskState.payload.children` and updates
the parent's `progress` as `sum(child_status==done) / len(children)`.

### 3. Sandbox directory layout

Each upload gets a per-request temp directory under
`<RKB_DATA_DIR>/sandbox/<library_id>/<request_id>/` with:

- `inbox/` — raw multipart payload (the ZIP, or the multi-file dump).
- `extracted/` — extracted contents, **never directly mounted** by the worker.
- `staging/` — validated PDFs, copied from `extracted/` after passing
  every check; this is the only path the worker reads from.

Directory cleanup on three triggers:

- Parent task `done` or `failed` — sweep after 60 s grace.
- Worker startup — sweep any orphan directories older than 1 h.
- Disk usage > 80% — emergency sweep oldest first.

### 4. Hard limits (constants in `packages/ingestion/limits.py`)

| Constant                          | Value     | Why                                                                  |
|-----------------------------------|-----------|----------------------------------------------------------------------|
| `MAX_ZIP_SIZE_BYTES`              | 500 MB    | Larger archives go through the CLI batch path, not the web upload    |
| `MAX_PDF_SIZE_BYTES`              | 100 MB    | Single PDF cap; rejects scanned-image PDFs that should be split      |
| `MAX_EXTRACTED_TOTAL_BYTES`       | 2 GB      | Zip-bomb hard ceiling for total expansion                            |
| `MAX_EXTRACTED_FILE_COUNT`        | 1000      | One ZIP can't carry 50k tiny files                                   |
| `MAX_NESTED_ZIP_DEPTH`            | 1         | We do not recursively unpack ZIPs inside ZIPs (defense in depth)     |
| `MAX_PATH_DEPTH`                  | 16        | Filesystem path components (no nested-folder DoS)                    |
| `MAX_FILENAME_LENGTH`             | 255       | OS limit; we reject earlier with a clean error                       |
| `MAX_PER_REQUEST_DISK_QUOTA`      | 5 GB      | Per-sandbox disk cap; enforced via stat polling during extraction    |
| `EXTRACTION_TIMEOUT_S`            | 120       | A well-formed 500 MB ZIP extracts in seconds; 2 min is a generous DoS cut |

These are **soft** in CLI mode (operator override) and **hard** through the
HTTP API (no override path).

### 5. Safe extraction algorithm

```python
# packages/ingestion/extractor.py — pseudocode
def extract_zip(library_id: str, zip_path: Path, sandbox: Path) -> ExtractionReport:
    if zip_path.stat().st_size > MAX_ZIP_SIZE_BYTES:
        raise ZipTooLarge(...)

    extracted_total = 0
    extracted_count = 0
    rejected: list[Rejection] = []

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            # 1. Reject path traversal & absolute paths
            if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                rejected.append(Rejection(info.filename, "path_traversal"))
                continue
            # 2. Reject symlinks (zipfile permission bits)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                rejected.append(Rejection(info.filename, "symlink"))
                continue
            # 3. Reject excessive depth
            if len(Path(info.filename).parts) > MAX_PATH_DEPTH:
                rejected.append(Rejection(info.filename, "deep_path"))
                continue
            # 4. Reject overlong file names
            if len(Path(info.filename).name) > MAX_FILENAME_LENGTH:
                rejected.append(Rejection(info.filename, "long_name"))
                continue
            # 5. Reject huge declared file size (catch zip-bombs early)
            if info.file_size > MAX_PDF_SIZE_BYTES * 5:
                rejected.append(Rejection(info.filename, "single_too_large"))
                continue
            extracted_total += info.file_size
            extracted_count += 1
            if extracted_total > MAX_EXTRACTED_TOTAL_BYTES:
                raise ZipBombSuspected(extracted_total)
            if extracted_count > MAX_EXTRACTED_FILE_COUNT:
                raise TooManyFiles(extracted_count)

            # 6. Resolve target path inside sandbox; verify with realpath
            target = (sandbox / info.filename).resolve()
            if sandbox.resolve() not in target.parents:
                rejected.append(Rejection(info.filename, "sandbox_escape"))
                continue

            # 7. Stream-extract with size cap (catch lying headers)
            with zf.open(info) as src, target.open("wb") as dst:
                copy_with_cap(src, dst, cap=MAX_PDF_SIZE_BYTES)

    return ExtractionReport(extracted_count, extracted_total, rejected)
```

Two non-obvious choices here:

- **`info.external_attr` symlink check** — Python's `zipfile` will happily
  create symlinks on some platforms, and a symlink in a ZIP is the canonical
  escape vector. We refuse them at the manifest level.
- **`target.resolve()` vs `sandbox.resolve()`** — both sides are realpath'd,
  so a `..` slipped past the manifest check is caught when the path resolves
  outside the sandbox root.

### 6. PDF discovery (post-extract)

After extraction, walk `extracted/` recursively. A file is a PDF iff:

- Extension `.pdf` (case-insensitive), AND
- First 5 bytes are `%PDF-` (magic number), AND
- Size is `0 < size <= MAX_PDF_SIZE_BYTES`.

Anything else is logged into the rejection list. We do **not** attempt to
parse non-PDFs or treat `.txt`/`.md` as documents in v1.

```python
def discover_pdfs(root: Path) -> list[Path]:
    pdfs = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".pdf":
            continue
        with path.open("rb") as f:
            head = f.read(5)
        if head != b"%PDF-":
            continue
        if not (0 < path.stat().st_size <= MAX_PDF_SIZE_BYTES):
            continue
        pdfs.append(path)
    return pdfs
```

### 7. Worker fan-out

```python
# apps/worker/jobs/ingest_batch.py — pseudocode
async def ingest_batch(ctx, library_id: str, sandbox: Path, parser: str, tags: list[str]):
    pdfs = discover_pdfs(sandbox / "extracted")
    children: list[str] = []

    # Pre-flight: cost cap (ADR-0015) — refuse the whole batch if estimated cost would breach 100%
    estimate = estimate_batch_cost(library_id, pdfs)
    if not check_daily_cost_allowance(library_id, estimate):
        raise DailyCostBlocked(library_id, estimate)

    for pdf in pdfs:
        sha = sha256_file(pdf)
        # Idempotency (ADR-0007 §4): skip if (library_id, sha) already done
        if ingest_state.is_done(library_id, sha):
            continue
        # Copy into staging (read-only zone for the worker)
        staged = stage_pdf(pdf, library_id)
        child_handle = await task_queue.enqueue(
            library_id,
            TaskSpec(
                library_id=library_id,
                task_type="ingest",
                input={"path": str(staged), "parser": parser, "tags": tags, "parent_task_id": ctx.task_id},
            ),
        )
        children.append(child_handle.task_id)

    await task_queue.set_payload(ctx.task_id, {"children": children, "discovered": len(pdfs)})
    return {"discovered": len(pdfs), "enqueued": len(children)}
```

Parent progress (ADR-0009 / §2.1 contract):

```
parent.progress = sum(1 for c in children if state(c) in {"completed","failed","cancelled"}) / len(children)
parent.status   = "completed" when every child is terminal AND at least one completed
                  "failed"    when every child is terminal AND none completed
                  "running"   otherwise
```

### 8. SSE event emission (ADR-0010)

`ingest_batch` emits the same event vocabulary as other long tasks; payloads
specific to batch:

| Event             | Payload                                                                |
|-------------------|------------------------------------------------------------------------|
| `task_queued`     | `{kind: "zip"|"folder", expected_pdfs?: int}`                          |
| `stage_started`   | `{stage: "extract"}` then `{stage: "discover"}` then `{stage: "fan_out"}` |
| `stage_progress`  | `{stage: "fan_out", current: 12, total: 47}`                            |
| `stage_completed` | `{stage: "extract", rejected: 3, accepted: 47}`                         |
| `task_completed`  | `{succeeded: 45, failed: 2, skipped_idempotent: 0}`                     |
| `task_failed`     | `{error_code: "ZIP_BOMB_SUSPECTED", message: "..."}`                    |

Per-child events come from the existing `ingest_document` job; the frontend
correlates them by `parent_task_id`.

### 9. Partial failure semantics

A child failure does **not** fail the parent. The parent's final state is
`completed` if at least one child completed, with `payload.failures` listing
each failed child's `(doc_path, error_code, suggestion)`. Frontend renders
this as a banner on the Documents table; failed rows expose the per-document
retry button (BACKEND_ROADMAP §3.6 Gap 3).

A notification (ADR-0011) is emitted once per parent at terminal:

| Outcome                              | severity | title                                              |
|--------------------------------------|----------|----------------------------------------------------|
| All children completed               | `info`   | "Ingested 47 PDFs from `papers.zip`"               |
| Some succeeded, some failed          | `warning`| "Ingested 45 of 47 PDFs (2 failed)"                |
| All failed                           | `danger` | "All 47 PDFs failed to ingest"                     |
| Extraction blocked (zip-bomb/etc.)   | `danger` | "Upload rejected: <reason>"                        |

### 10. Idempotency and re-uploads

Re-uploading a folder/ZIP that contains already-ingested PDFs:

- Each PDF is hashed; the `is_done(library_id, sha)` check from ADR-0007 §4
  shortcircuits.
- The `ingest_batch` parent reports `skipped_idempotent` count alongside
  `succeeded` and `failed`.
- No embeddings are recomputed. No KG re-extraction. No cost charged.
- The user-facing notification reads `"42 already indexed, 5 newly added"`.

This is the same idempotency guarantee as single-PDF upload, generalized to
the batch.

## Consequences

### Positive

- **S6 prototype unblocked.** Drag-drop folder works, with progress per
  PDF and a single completion notification.
- **Safety floor.** Zip-bomb, path traversal, and symlink escape are caught
  at the manifest layer, before disk I/O. Dec ompression always streams
  through a size cap.
- **Idempotent batches.** Re-running a 200-PDF folder costs zero embedding
  cycles when nothing changed.
- **Composable with existing infra.** No new queue, no new event schema, no
  new error envelope; reuses ADR-0009 / 0010 / 0007.

### Negative

- **No nested ZIPs in v1.** A user who packs `inner.zip` inside `outer.zip`
  gets a clean error. Operator workaround is to repack flat. Acceptable
  trade-off for the safety bound; reopen if real users complain.
- **Disk pressure on big batches.** 500 MB ZIP × parallel uploads can
  saturate sandbox disk. Mitigated by per-request quota and global
  emergency sweep, but the worker box must have ≥ 20 GB free in
  `<RKB_DATA_DIR>/sandbox/`. Documented in OPERATOR_RUNBOOK.
- **Walk-then-fan-out is single-process.** Discovery runs on the worker
  thread that owns the parent job; very large folders (>1000 files) are
  rejected at extraction time (`MAX_EXTRACTED_FILE_COUNT`).

### Risks

| Risk                                                  | Mitigation                                                                                          |
|-------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Malicious ZIP (zip-bomb)                              | Streaming extract with `cap=MAX_PDF_SIZE_BYTES` per file + `MAX_EXTRACTED_TOTAL_BYTES` global cap   |
| Path traversal / sandbox escape                       | Manifest-level reject + `realpath` containment check + symlink reject                               |
| Symlink-based escape on ZIPs                          | `external_attr` symlink-bit reject before write                                                     |
| Long filename DoS                                     | `MAX_FILENAME_LENGTH=255` reject before write                                                       |
| Disk exhaustion on the worker box                     | Per-request 5 GB quota; global 80% emergency sweep; OPERATOR_RUNBOOK documents `df -h` watchpoint   |
| Idempotency cache bypass via `--force`                | `--force` is CLI-only and not exposed via HTTP API; it bypasses the dedupe but still hits all caps  |
| Cost cap blow-up on batch                             | Pre-flight `estimate_batch_cost` + per-child cap recheck (ADR-0015)                                 |
| Lying multipart `Content-Type`                        | Header is logged but not trusted; the magic number on first read is authoritative                   |
| Concurrent uploads racing on disk quota               | Per-request quota is enforced via stat polling; new uploads bounce when global sandbox > 80%        |

## Alternatives Considered

| Option                                  | Rejected Because                                                                                              |
|-----------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **Front-end ZIP unpack**                | Browser ZIP libraries are uneven; large folders OOM the tab; we lose the server-side hash chain (ADR-0007)    |
| **Recursive nested-ZIP support**        | Adds an attack surface; users can flatten before upload; v2 if real demand emerges                            |
| **Direct write to MinIO from API (no sandbox)** | Loses the inspect-and-validate gate; a malicious payload streams straight into long-term storage      |
| **Single endpoint, sniff `Content-Type`** | Less explicit than the `kind=` discriminator; ambiguous for multi-file folder uploads                       |
| **Background unpack with synchronous response** | UI feels faster but blocks API workers; conflicts with ADR-0009's queue-everything stance              |
| **No size caps, rely on filesystem quotas** | Filesystem quotas vary by OS and aren't always available; explicit caps in user-space are portable        |
| **Accept tar.gz in addition to ZIP**    | One archive format = one attack surface; tar's symlink semantics need separate handling; defer to v2          |

## Open Questions

1. **Should `kind=folder` accept ≥ 1000 files via streaming multipart?**
   Today the cap is 1000 files for ZIPs. The folder path goes through
   browser multipart which has its own limits; we set the same cap for
   parity. Reopen if a real user hits it.
2. **Per-Library disk quota.** Today the 5 GB sandbox quota is global per
   request. Should it also enforce a per-Library running total (sum of
   active sandboxes)? Provisional answer: yes, in a follow-up — track as
   a small feature on top of ADR-0012.
3. **Should the rejection list return per-file error codes for the UI?**
   Today: yes, structured `[{path, code, suggestion}]` in
   `task_completed.payload.rejected`. Confirm UI consumes it.
4. **Encrypted ZIPs.** We refuse them today (no password input path).
   Reopen when an actual researcher complains.
5. **Worker-side virus scan.** ClamAV integration is out of scope for v1.
   The PDF-only discovery + magic-number gate is our v1 floor; if a user
   smuggles a malicious PDF, that is the parser's problem, not the
   extractor's.

## Relationships With Other ADRs

- **ADR-0001 (Modular Monolith)** — `extractor.py` and `batch_ingestor.py`
  live under `packages/ingestion/`. The `BatchIngestor` Protocol is the
  single seam orchestration calls. No cross-package shortcut.
- **ADR-0003 (Library as Data Partition)** — every extracted PDF inherits
  `library_id`. There is no cross-Library batch upload path.
- **ADR-0007 (Error Envelope + Idempotency)** —
  - Error codes: `ZIP_TOO_LARGE`, `ZIP_BOMB_SUSPECTED`, `ZIP_PATH_TRAVERSAL`,
    `ZIP_SYMLINK`, `TOO_MANY_FILES`, `EXTRACTION_TIMEOUT`,
    `DAILY_COST_BLOCKED` map to the `RKBError` family.
  - Idempotency reuses `(library_id, file_sha256)` from ADR-0007 §4 for
    every child PDF.
- **ADR-0009 (Async Task Queue)** — `ingest_batch` is registered as a queue
  job; child `ingest_document` tasks run on the same queue. Parent-child
  progress aggregation is implemented at the queue layer.
- **ADR-0010 (SSE Stage Events)** — Event vocabulary in §8 reuses the
  standard set; batch-specific payloads documented but no new event types
  added (the stability promise holds).
- **ADR-0011 (Notification Center)** — Single terminal notification per
  parent; severity matrix in §9.
- **ADR-0015 (Daily Cost Cap)** — Cost estimate computed at fan-out;
  pre-flight refusal + per-child recheck. Block at 100%, warn at 80%.

## References

- PRD §8.2 (M1 Ingestion scope), §14.2 (M7 UX — drag-drop folder),
  §16.6 (Library discipline), §17 R02 (parser fallback chain pattern)
- BACKEND_ROADMAP §3.6 Gap 1 (ZIP/folder upload), §3.6 Gap 3 (per-doc
  retry), §3.6 Gap 4 (structured ingest errors), §5 (ADR-0019 line item),
  §2.1 (Arq queue), §2.7 (daily cost cap)
- OWASP "Path Traversal" cheat sheet — design baseline for §5
- CWE-409 "Improper Handling of Highly Compressed Data (Data Amplification)"
  — design baseline for `MAX_EXTRACTED_TOTAL_BYTES`
- `packages/ingestion/state.py` (ADR-0007) — reused for child idempotency
- `apps/worker/jobs/ingest_document.py` (ADR-0009) — the child job this
  batch fans out to
