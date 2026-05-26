# RAG-KG Copilot — User Guide

Audience: researchers (PhD students, postdocs, engineers) who want to turn a
PDF corpus into a queryable knowledge assistant. No infra knowledge required.

## What you get

- **Ask** questions in natural language and get **cited** answers with chunk-level provenance
- **Browse** the knowledge graph of entities + relations extracted from your papers
- **Generate** literature reviews and KG-grounded hypotheses on demand
- **Stay isolated**: each "Library" is a fully separate corpus + index + KG; no cross-bleed

## Core concept: Library

A **Library** is the unit of physical isolation. One subject area = one Library. Examples:

- `rag-agent` (your reading on RAG + agent architectures)
- `protein-binding` (a different research thread)

Why it matters:
- Search results, KG views, stats are **always scoped to the current Library**.
- Switching Libraries clears the page state — no leak between topics.
- Backups, deletes, and quotas all work at Library granularity.

A Library ID is a slug (lowercase + dashes, 3–31 chars): `rag-agent`, `protein-binding`.

## 15-minute first run

### 1. Pick / make a Library

In the Web UI: top bar → **Library Switcher** → **+ New library**. Type a slug, name, optional description.

In CLI:
```
uv run rkb library create rag-agent --name "RAG + Agent reading"
```

### 2. Upload PDFs

Web UI: switch to the new Library → **Upload** tab → drag PDFs in (≤ 50 MB each, PDF only). Progress bar per file. Re-uploading the same PDF is a no-op (idempotent by SHA-256).

CLI:
```
uv run rkb ingest --library rag-agent path/to/papers/
```
Add `--force` to re-ingest a file even if it has already been done.

### 3. Ask a question

Web UI: **QA** tab → type a question → press Enter.

You'll get a streaming answer with `[chunk_id]` markers. Click any marker to see the source chunk, document, page, and snippet. **The frontend only renders citations the backend returned** — there is no hallucinated provenance.

CLI:
```
uv run rkb qa --library rag-agent --question "What is GraphRAG?"
```

### 4. Explore the KG

Web UI: **Knowledge Graph** tab → type an entity name → click search. You see a force-directed graph (max 50 neighbors by default to keep the canvas usable). Click a node to expand its neighborhood.

CLI:
```
uv run rkb library neighborhood --library rag-agent --entity GraphRAG --depth 2
```

### 5. Generate a review

Web UI: **Review** tab → enter a topic → submit.

CLI:
```
uv run rkb review --library rag-agent --topic "Hybrid retrieval techniques"
```

## Citations: the contract

Every factual claim in an answer **must** be backed by a `[chunk_id]` that
appears in the `citations` list returned by the backend. If the model couldn't
find supporting evidence in your Library, it will say so explicitly rather
than guess. This is enforced at three layers:

1. The QATask LLM prompt requires inline citations
2. The frontend filters out any `[id]` not present in `citations[]`
3. The eval harness checks Citation F1 in CI

## Per-Library isolation, in practice

| You do… | What happens behind the scenes |
| --- | --- |
| Switch Library in the top bar | qaStore / kgStore / statsStore are wiped; URL flips to `/libraries/<new-id>/...` |
| Delete a Library | Postgres rows + Qdrant collection + Neo4j subgraph + MinIO prefix all purged |
| Run `library export` | Single tar.gz with corpus + KG + community summaries + ingest state |
| `library import --as <new-id>` | Creates a fresh Library with a different id; restores corpus; you re-run `ingest` to repopulate indices |

## i18n

Two locales out of the box: 简体中文 and English. Switch from the top-right
selector. Persisted in localStorage. Submit translations as PRs to
`apps/web/src/i18n/locales/`.

## Auth (optional)

If you set `API_KEY` in `.env`, every request must include
`Authorization: Bearer <token>`. If empty (default), the system runs as
anonymous — fine for solo desktop use.

## Cost awareness

LLM calls and embeddings cost money. The system is built for **frugal**
research workflows:

- Embedding cache (sqlite) — same text never re-embedded
- Ingest is idempotent — same PDF re-uploaded = no-op
- KG extraction is gated by schema; raw extraction off by default in dev
- The retrieval planner picks the cheapest valid mode (direct → hybrid → routed → ReAct)
- All LLM/embedding/cost metrics surfaced on `/metrics` (Prometheus)
- Optional rate limit (`rate_limit_enabled`) caps per-route throughput

## Where to go next

- Operator concerns (logs, dashboards, troubleshooting): `docs/OPERATOR_RUNBOOK.md`
- HTTP API reference: `docs/API_REFERENCE.md`
- 3 worked examples: `docs/examples/01_create_library.ipynb`,
  `02_ingest_papers.ipynb`, `03_qa_with_kg.ipynb`
