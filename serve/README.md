# RAG-KG Copilot

A self-hosted research Copilot that builds dense knowledge graphs from your literature and answers questions with traceable citations.

**Status**: M0–M8 完成（评测系统 + 上下文管理 + Vue 3 前端均已上线）

## What It Does

- **Ingest** PDFs and papers into isolated Libraries (one per research domain)
- **Build** a knowledge graph with entities, relations, and provenance
- **Retrieve** via hybrid search: dense vectors + sparse BM25 + graph traversal + community summaries
- **Answer** with agent-driven retrieval, citation verification, and multi-hop reasoning
- **Evaluate** continuously with per-Library gold-standard test sets

## Architecture

Five-layer modular monolith with strict dependency direction:

```
apps (api / worker / cli)
  |
  v
orchestration (L5) --> retrieval (L4) --> indexing (L3)
                                      --> structuring (L2)
                                      --> ingestion (L1)
                        |
                        v
                   llm / embedding
                        |
                        v
                     eventbus
                        |
                        v
                       core
```

**Data layer**: Postgres + Qdrant + Neo4j + OpenSearch + Redis + MinIO

Each storage backend physically isolates data by Library (separate collections, databases, indexes, and prefixes).

## Library Concept

A **Library** is a self-contained research corpus — think "one library per research topic."
- You manually collect papers/materials for a domain and ingest them into a Library
- All queries are scoped to a single Library
- Libraries are physically isolated in every storage backend
- See [ADR #3](docs/adr/0003-library-as-data-partition.md) for design rationale

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker + Docker Compose

### 5 Steps

```bash
# 1. Clone and install
git clone <repo-url> && cd rag-kg-copilot
make install          # uv sync

# 2. Start data layer
make up               # docker compose up -d (Postgres, Qdrant, Neo4j, OpenSearch, Redis, MinIO)

# 3. Verify health
make api              # starts FastAPI on :8000
curl http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}

# 4. Run quality gates
make lint             # ruff check + format
make typecheck        # pyright --strict
make test             # pytest
make test-cov         # pytest with coverage gate (80%)

# 5. Explore CLI
make cli -- version
make cli -- library list
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via uv |
| `make up` / `make down` | Start / stop data layer containers |
| `make api` | Run FastAPI dev server |
| `make worker` | Run Arq async worker |
| `make cli` | Run CLI |
| `make lint` | Ruff lint + format check |
| `make typecheck` | Pyright strict |
| `make test` | Run all tests |
| `make test-cov` | Tests with 80% coverage gate |

## Project Structure

```
rag-kg-copilot/
├── apps/                  # Executable entry points
│   ├── api/               # FastAPI service
│   ├── worker/            # Arq background worker
│   └── cli/               # Typer CLI (rkb)
├── packages/              # Domain modules
│   ├── core/              # Domain models, config, errors (zero deps)
│   ├── eventbus/          # In-memory event bus
│   ├── ingestion/         # L1: Parse, chunk, deduplicate
│   ├── structuring/       # L2: NER, relation extraction, entity linking
│   ├── indexing/          # L3: Vector, graph, BM25, community indexes
│   ├── retrieval/         # L4: Agent-based retrieval planning
│   ├── orchestration/     # L5: Task templates (QA, review, hypothesis)
│   ├── llm/               # LLM gateway (stateless)
│   ├── embedding/         # Embedder + reranker (stateless)
│   └── evaluation/        # Eval subsystem (terminal package)
├── infra/                 # Docker Compose, future Helm/Terraform
├── tests/                 # Unit, integration, e2e, evals
├── docs/
│   └── adr/               # Architecture Decision Records
└── pyproject.toml         # Single project config
```

## Roadmap

| Milestone | Status | Capability |
|-----------|--------|------------|
| M0 Foundation | ✅ Done | Repo skeleton, CI, data layer, domain models |
| M1 MVP-RAG | ✅ Done | PDF ingest, vector search, end-to-end QA with citations |
| M2 GraphFusion | ✅ Done | Knowledge graph extraction, hybrid retrieval, reranking |
| M3/M4 AgentLoop | ✅ Done | Leiden communities, global search, agentic retrieval (Self-RAG / CRAG / ToG) |
| M5 Tasks | ✅ Done | Literature review, cross-paper reasoning, hypothesis generation |
| M6 QualityLoop | ✅ Done | 8-metric eval (5 deterministic + 3 LLM-judge), Langfuse, OTel, CI gate |
| M7 Hardening | ✅ Done | Vue 3 web UI, OpenAPI 契约, ingest 幂等, library 备份, 安全审查 |
| M8 Context | ✅ Done | 多轮会话、研究记忆、query 改写 |

> 异步任务说明：当前所有任务（ingest / QA / review / reason）在 CLI/API 进程内同步执行，**arq worker 进程目前是脚手架**，不参与实际工作流。`apps/worker/main.py` 里的 `noop` 函数只是为了让 worker 进程能启动通过 arq 的 `functions 非空` 校验。如果未来需要把 ingest 之类的耗时任务异步化，再在 `WorkerSettings.functions` 里注册真实任务即可。

## ADRs

- [0001 — Modular Monolith](docs/adr/0001-modular-monolith.md)
- [0002 — Toolchain Selection](docs/adr/0002-toolchain-selection.md)
- [0003 — Library as Data Partition](docs/adr/0003-library-as-data-partition.md)

## Contributing

See [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) for code conventions, and [`docs/AGENT_PROMPT.md`](docs/AGENT_PROMPT.md) for the implementation workflow.

Key principles:
- Interface before implementation (`protocols.py` first)
- Immutable data models (`frozen=True, extra="forbid"`)
- Test-driven development (write tests first, 80%+ coverage)
- `library_id` as first field on all cross-library models
- No `Any` types; pyright strict
