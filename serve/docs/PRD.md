# PRD & Roadmap — RAG-KG Copilot

**产品**：面向科研的稠密本地知识库 + Agent Copilot
**代号**：`rag-kg-copilot`
**文档状态**：v0.2 / Draft（加入多 Library 数据分区维度）
**最后更新**：2026-04-25
**Owner**：待定
**配套文档**：[`CODING_STANDARDS.md`](./CODING_STANDARDS.md)

> 本文档定义愿景、范围、成功指标、以及 **M0 → M8 共 9 个里程碑**的交付边界与退出条件。任何开发动作必须对齐某个里程碑的 Exit Criteria；任何新增范围必须进本文件并更新路线图。

---

## 目录

- [0. 执行摘要](#0-执行摘要)
- [1. 愿景与问题陈述](#1-愿景与问题陈述)
- [2. 目标用户与使用场景](#2-目标用户与使用场景)
- [3. 成功指标](#3-成功指标)
- [4. 范围与非目标](#4-范围与非目标)
- [5. 系统架构回顾](#5-系统架构回顾)
- [6. 里程碑总览](#6-里程碑总览)
- [7. M0 — 工程地基](#7-m0--工程地基)
- [8. M1 — Minimum Viable RAG](#8-m1--minimum-viable-rag)
- [9. M2 — 知识图谱与混合检索](#9-m2--知识图谱与混合检索)
- [10. M3 — Community 与全局检索](#10-m3--community-与全局检索)
- [11. M4 — Agentic Retrieval](#11-m4--agentic-retrieval)
- [12. M5 — 科研任务模板](#12-m5--科研任务模板)
- [13. M6 — 评测与可观测](#13-m6--评测与可观测)
- [14. M7 — 硬化与用户体验](#14-m7--硬化与用户体验)
- [15. M8 — 面向未来的扩展](#15-m8--面向未来的扩展)
- [16. 横切关注点](#16-横切关注点)
- [17. 风险登记册](#17-风险登记册)
- [18. 发布与版本策略](#18-发布与版本策略)
- [附录 A — 里程碑甘特草图](#附录-a--里程碑甘特草图)
- [附录 B — 交付物清单总表](#附录-b--交付物清单总表)

---

## 0. 执行摘要

构建一个**个人/小组可自托管**的科研 Copilot，能从 PDF 文献出发自动建立**稠密知识图谱 + 多索引检索层**，并以 **Agent 编排**完成"问答 / 综述 / 跨文献推理 / 假设生成"四类科研任务。

**横向扩展能力**：系统支持多个独立 **Library（资料库）**，每个 Library 对应一个研究方向（领域）—— 用户手动收集该领域的论文/资料后，按 Library 灌入；查询时显式指定 Library。Library 是**数据分区**而非架构层（详见 `CODING_STANDARDS §6.5`），不增加任何包、不改变分层。

**一年目标**：从零到 v1.0 —— 至少在一个具体研究方向上（首个 Library），实现"导入 ≥ 2000 篇论文 → 高质量带引用问答 → 可交互式综述 → 多跳跨文献推理"的端到端闭环；同时验证多 Library 横向扩展能力（可独立创建/隔离/清除 ≥ 2 个 Library）。

**开发策略**：**模块化单体**（Modular Monolith）起步，严格按 `CODING_STANDARDS.md` 的分层与接口约束。里程碑之间**纵向切片**，每个里程碑结束都有可运行、可展示、可评测的产物。

---

## 1. 愿景与问题陈述

### 1.1 Vision（一句话）

**让一个人，也能像一支团队那样，跟上并深耕一个科研方向。**

### 1.2 Problem

1. **文献洪流**：单一子方向每月新增数百篇，研究者无法跟读。
2. **LLM 幻觉**：普通 ChatGPT 类工具答题无可追溯引用，无法用于严肃科研。
3. **检索失效**：向量 RAG 在多跳、跨文献、需要结构化关系的问题上失效。
4. **工具割裂**：PaperQA / Elicit / ResearchRabbit 各解其一环，缺乏统一的"稠密本地 KB + Agent"底座。

### 1.3 解决思路

把**知识图谱**当作"论文间关系的结构化记忆"，把**多索引检索**当作"稠密性保障"，把**Agent 编排**当作"任务闭环的大脑"—— 三者合一，构成面向科研的 Copilot。

**资料组织**：每个研究方向独立成一个 **Library**（资料库），用户手动收集该领域的稠密资料（论文、专利、教材、笔记、实验日志）灌入；多个 Library 可并存且互不干扰，查询时按需切换。

---

## 2. 目标用户与使用场景

### 2.1 Primary Persona

- **博士/博后**：跟某一子方向深耕 3+ 年，积累数百到数千篇论文。
- **小型课题组**：3–10 人，共享同一领域文献库。

### 2.2 核心场景（P0）

| 场景 ID | 描述 | 输入 | 输出 |
|--------|------|------|------|
| **UC0**: Library 管理 | 创建 / 列表 / 切换 / 删除资料库 | Library ID + 元数据 | 隔离的资料库实例 |
| **UC1**: 精准问答 | "X 方法在 Y 场景的表现如何？"（在指定 Library 内） | 自然语言 + library_id | 带引用答案 + 证据片段 |
| **UC2**: 实体透视 | "给我看看 GraphRAG 这个概念的关联网络" | 实体名 + library_id | KG 子图 + 摘要 |
| **UC3**: 主题综述 | "近 2 年图神经网络+药物重定位的进展" | 主题 + library_id | 结构化综述草稿 + 引用 |
| **UC4**: 跨文献推理 | "A 团队的方法被 B 场景验证过吗？" | 多跳问题 + library_id | 路径 + 证据 + 结论 |
| **UC5**: 假设生成（P1） | "给定目标：找一个新的药物靶点" | 目标描述 + library_id | 候选假设 + 评分 + 证据链 |

> **隐含约束**：UC1–UC5 的所有操作都限定在**单个 Library**内；不支持单次查询跨 Library。需要"对比两个领域"时由用户分别问两次。

### 2.3 非用户

- 对答案正确性不敏感的通用聊天用户。
- 企业级多租户生产用户（v1 范围外）。

---

## 3. 成功指标

### 3.1 North Star

**单次完整研究问答的有效率（Valid Answer Rate, VAR）**
> 定义：用户提问 → 收到带引用答案 → 用户标记"有用 + 引用正确" 的比例。
> 目标：**v1.0 达成 ≥ 75%**（在目标领域的 100 题金牌评测集上）。

### 3.2 护栏指标（Guardrails）

| 维度 | 指标 | 目标 |
|------|------|------|
| **引用忠实度** | Citation F1（Claim-Evidence 对齐） | ≥ 0.85 |
| **检索召回** | Recall@10（多跳 QA） | ≥ 0.70 |
| **端到端延迟** | P95 响应时间 | ≤ 20s（QA 模式） |
| **摄取吞吐** | 每小时入库论文数 | ≥ 50（单机 GPU） |
| **LLM 成本** | 每题平均 token 花费 | ≤ $0.10（目标领域） |
| **代码质量** | 测试覆盖率 | ≥ 80% |
| **架构合规** | tach 违规数 | = 0 |

### 3.3 Leading Indicators

- 每个里程碑结束时 Exit Criteria 100% 达成。
- ADR 数量稳定增长（架构决策留痕）。
- 评测集规模每月扩充 ≥ 20 题。

---

## 4. 范围与非目标

### 4.1 v1 In Scope

- 单用户 / 小组共享、本地/自托管部署。
- **多 Library 横向扩展**：用户手动收集资料，按领域建 Library；查询时显式指定。Library 是数据维度，不是架构（详见 `CODING_STANDARDS §6.5`）。
- 第一个 Library 锁定一个具体研究方向（用户择定，例如 "GraphRAG 与图上推理"）；至少验证 ≥ 2 个 Library 并行不互扰。
- 文献源：arXiv / PubMed / OpenAlex / 本地 PDF（用户手动收集）。
- **批量上传**：单 PDF / ZIP 包 / 文件夹（带子目录）拖拽上传，后端展开后按内容哈希幂等去重。
- UI：Web（chat + 文档上传 + KG 浏览 + 综述/推理/假设任务 + 评测仪表盘 + Library 切换）+ CLI。
- 中英文混合语料；UI 支持 zh-CN + en-US 双语切换（vue-i18n）。
- **per-Library 配置覆盖**（M7 落地）：每个 Library 可独立配置 LLM 路由 / Embedder / 检索预算 / 每日成本上限；未覆盖的项继承全局默认值（详见 §14.2）。

### 4.2 Out of Scope / Non-Goals

| 项 | 理由 |
|----|------|
| **多租户 / 鉴权 / 计费 / SaaS** | 多 Library ≠ 多租户；前者是数据分区，后者是身份隔离。v1 不做身份/权限/计费。 |
| **跨 Library 联合查询** | 单查询跨多个 Library；先用客户端多次调用解决，v2+ 再考虑底层支持 |
| 移动端 / iOS/Android | 非主要使用场景 |
| 自动跑湿实验 | 超出定位 |
| 完整 AI Scientist-v2 等级的自主科研 | v2+ 目标 |
| 商业闭源模型独占依赖 | 必须支持全本地方案 |
| 实时（秒级）同步外部数据源 | 每日批同步即可 |

### 4.3 显式延后（v1.1+）

- 假设生成的 KG embedding 路径挖掘
- Hypothesis tournament（AI co-scientist 风格）
- 多用户协作 / 评论 / 标注
- 跨 Library 联合查询与差异分析（v1 仅允许 L5 编排层组合**只读元视图**，不允许跨库数据查询；详见 §16.6）
- 插件化外部工具（Wolfram / 代码执行）
- 移动端 / iOS / Android（v1 仅 Web）

---

## 5. 系统架构回顾

五层模块化单体（详见 `CODING_STANDARDS.md §2-§3`）：

```
apps  →  orchestration (L5)  →  retrieval (L4)  →  indexing (L3)
                                                 ↘  structuring (L2)
                                                 ↘  ingestion (L1)
                                  ↓
                          {llm, embedding}
                                  ↓
                              eventbus
                                  ↓
                                core
```

**Library 维度（正交于上图）**：所有 L1–L5 的操作都按 `library_id` 物理分区。架构层不感知 Library 的存在，只是把 `library_id` 当成"必填的分区键"透传到适配器；适配器在每个存储后端按其原生方式做物理隔离（Qdrant collection / Neo4j composite DB / Postgres `library_id` 列 / OpenSearch index / MinIO prefix；详见 `CODING_STANDARDS §12.5`）。

```
                  L1–L5 (架构 / 行为)
                         │
                         ▼  所有调用都带 library_id
              ┌─────────────────────┐
              │  Library A   B   C   ...
              │  (数据 / 命名空间)
              └─────────────────────┘
```

**三个进程**：`apps/api`（在线） + `apps/worker`（异步摄取） + LLM 推理后端。
**数据层**：Postgres + Qdrant + Neo4j（或 Kuzu）+ OpenSearch（或 BM25S）+ Redis + MinIO。每个后端按 `library_id` 做物理隔离。

**本地数据组织**：每个 Library 对应 `data/libraries/<library_id>/`，含语料目录（`corpus/`）和评测集（`evals/`）。语料为大文件不入 git；评测集 YAML 纳入版本控制。评测集支持自动生成（灌入后 LLM 从 chunk 生成 QA 对）+ 人工审核。详见 `data/README.md` 与 `docs/EVAL_ARCHITECTURE.md §11.5`。

---

## 6. 里程碑总览

| # | 里程碑 | 周期（周） | 主要能力 | Library 维度 | 外部可见产物 |
|---|-------|----------|---------|-------------|-------------|
| **M0** | 工程地基 | 2 | 仓库骨架 / CI / 数据层 / 核心模型 | `Library` 模型 + `library_id` 字段贯穿；ADR 定隔离策略 | `docker-compose up` 即可；核心 Protocol 定义完成 |
| **M1** | Minimum Viable RAG | 3 | PDF 摄取 + 向量检索 + 最简 QA | Library CRUD + 物理分区（Qdrant collection / Postgres 列） | 能提问得引用答案；可建删 Library |
| **M2** | KG + 混合检索 | 3 | NER/RE/EL + 图索引 + BM25 + Rerank | KG / BM25 按 Library 物理分区；Schema 可 per-Library | 多跳问题可答 |
| **M3** | Community 全局检索 | 2 | Leiden 社区 + 摘要 + Global Search | Community 摘要 per-Library 计算与缓存 | "领域综合性"问题可答 |
| **M4** | Agentic Retrieval | 3 | Self-RAG/CRAG 反思 + ToG 多跳 + Critic | Agent 全程限定 library scope；Trace 含 library_id | 鲁棒多跳 + 引用自检 |
| **M5** | 科研任务模板 | 3 | 综述生成 + 跨文献推理 + 假设生成（基础） | 任务限定单 Library；预算/成本 per-Library 计 | UC3 / UC4 / UC5 基础版 |
| **M6** | 评测与可观测 | 2 | Ragas + Langfuse + 金牌评测集 CI | 评测集 per-Library；Dashboard 加 Library 过滤 | 每次 PR 自动评测 |
| **M7** | 硬化与 UX | 3 | Web UI + 鉴权 + 错误恢复 + 文档完善 | UI Library 切换器；备份/恢复支持 per-Library | 真用户可用 |
| **M8** | 面向未来 | 持续 | 性能基线 / 抽服务预演 / v2 预研 | 跨 Library 联合查询、Library 配置覆盖等 v2 候选 | v2 ADR + 性能报告 |

**累计**：约 **21 周**（5 个月）达到 v1.0，之后进入 M8 持续演进。

**依赖关系**：
```
M0 → M1 → M2 → M3 ─┐
              └─ M4 ┴─ M5 ─ M6 ─ M7 ─ M8
```

M4 可以在 M3 完成后并行启动（但 M5 依赖 M4）。

---

## 7. M0 — 工程地基

**代号**：Foundation
**周期**：2 周
**前置依赖**：无

### 7.1 目标

搭好仓库骨架、工具链、CI 红线、数据层 compose、领域核心模型。**不写任何业务功能**，让之后所有代码都有规范的"生长土壤"。

### 7.2 Scope

**In**：
- Monorepo 目录（见 `CODING_STANDARDS §2.1`）
- `pyproject.toml` + uv workspace + 锁文件
- Ruff / Pyright strict / Tach 配置
- GitHub Actions：lint + type + unit test + arch check
- pre-commit 钩子（ruff / gitleaks）
- `infra/docker-compose.yml`：Postgres + Qdrant + Neo4j + Redis + MinIO + OpenSearch
- `packages/core/models.py`：**`Library`**, `Document`, `Chunk`, `Entity`, `Triple`, `Query`, `EvidenceRecord`（所有跨 Library 模型首字段为 `library_id: str`）
- `packages/core/events.py`：领域事件骨架（事件 payload 含 `library_id`）
- `packages/eventbus/`：in-memory 实现 + Protocol
- `packages/core/config.py`：Settings（pydantic-settings）
- 空包骨架：`ingestion/`, `structuring/`, `indexing/`, `retrieval/`, `orchestration/`, `llm/`, `embedding/`, `evaluation/`，每个含 `protocols.py` + `service.py` 占位；所有跨 Library 的 Protocol 方法签名首参为 `library_id: str`，并预留 `init_library` / `purge_library`
- **`packages/core/library_admin.py`**：薄 helper，按顺序调用各适配器的 `init_library` / `purge_library`（不开新 package，仅一个文件）
- `apps/api/main.py`：一个 `/healthz` 返回 200
- `apps/worker/main.py`：Arq 空 worker 能启动
- `apps/cli/main.py`：Typer 骨架；预留 `--library` 全局 flag
- Makefile：install/up/down/api/worker/test/lint/typecheck/arch
- `docs/adr/0001-modular-monolith.md`
- `docs/adr/0002-toolchain-selection.md`
- `docs/adr/0003-library-as-data-partition.md` —— 阐明 Library 是数据维度而非架构层；列出每后端的物理隔离方式
- `README.md`：本地启动 5 步

**Out**：
- 任何业务实现
- LLM 接入
- 任何 adapter
- Library 管理 API（仅留 Protocol 与数据模型；CRUD 实现在 M1）

### 7.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D0.1 | 仓库骨架 + uv workspace | `uv sync` 成功 |
| D0.2 | CI 流水线 | PR 触发 7 个 check 全绿 |
| D0.3 | 数据层 docker-compose | `make up` 后 6 服务健康 |
| D0.4 | 核心领域模型 + 事件 + `Library` 模型 | 单测覆盖 ≥ 90%；`library_id` 字段贯穿 |
| D0.5 | 所有 package 的 Protocol 骨架（含 `init_library` / `purge_library`） | `tach check` 通过 |
| D0.6 | `/healthz` endpoint | curl 返回 200 |
| D0.7 | README 起步指南 | 新机器照 README 10 分钟内跑起 |
| D0.8 | ADR #1 + #2 + #3 | 三份文件存在并通过 review |

### 7.4 要定义的接口（最小集）

```python
# packages/eventbus/protocols.py
class EventBus(Protocol):
    def subscribe(self, topic: str, handler: EventHandler) -> None: ...
    async def publish(self, topic: str, event: DomainEvent) -> None: ...

# packages/ingestion/protocols.py
class Parser(Protocol): ...
class Chunker(Protocol): ...
class Deduper(Protocol): ...

# packages/indexing/protocols.py
class VectorIndex(Protocol):
    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...
    # search/upsert 在 M1 定，签名首参 library_id

class GraphIndex(Protocol): ...      # 同样含 init/purge_library
class BM25Index(Protocol): ...       # 同样
class RetrievalCoordinator(Protocol): ...

# packages/llm/protocols.py
class LLMClient(Protocol): ...

# packages/embedding/protocols.py
class Embedder(Protocol): ...
class Reranker(Protocol): ...
```

**Library 生命周期编排**（不开 service，仅一个 helper）：

```python
# packages/core/library_admin.py
async def init_library(library_id: str, *, registries: LibraryAdmins) -> None:
    """Initialize a Library across all storage adapters."""
    for adapter in registries.all():
        await adapter.init_library(library_id)

async def purge_library(library_id: str, *, registries: LibraryAdmins) -> None:
    """Physically purge a Library from all storages."""
    for adapter in registries.all():
        await adapter.purge_library(library_id)
```

具体方法签名可在 M1 完成。M0 只要求**类占位 + 关键方法的签名空壳 + library 生命周期 helper**。

### 7.5 数据模型（M0 版）

```python
class Library(BaseModel):
    library_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,30}$")  # slug
    name: str
    description: str | None = None
    created_at: datetime

class Document(BaseModel):
    library_id: str          # 数据分区键（首字段）
    doc_id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    source_url: str
    doi: str | None
    content_hash: str        # SHA-256 of raw file
    ingest_ts: datetime

class Chunk(BaseModel):
    library_id: str
    chunk_id: str            # f"{doc_id}::{section}::{idx}"，library 内唯一即可
    doc_id: str
    text: str
    page: int | None
    section: str | None
    kind: Literal["text", "formula", "table", "caption"]
    offset: tuple[int, int]  # char span in doc

class Entity(BaseModel):
    library_id: str
    entity_id: str           # canonical ID（library 内唯一）
    name: str
    aliases: list[str]
    type: str
    description: str | None

class Triple(BaseModel):
    library_id: str
    head: str                # 必须与 head Entity 同 library_id
    relation: str
    tail: str
    evidence: list[str]      # chunk_ids（必须同 library_id）
    confidence: float
    source_model: str
```

全部 `frozen=True, extra="forbid"`。
**约束**：`(library_id, *)` 是唯一键；跨 Library 引用视为非法（在 Pydantic validator 中校验）。

### 7.6 测试要求

- 核心模型序列化 / 反序列化 roundtrip 测试
- EventBus 单元测试（pub/sub 基本语义）
- healthz 集成测试
- 覆盖率 ≥ 80%

### 7.7 Exit Criteria（DoD）

- [ ] 新同事从 git clone 到 `make up && make api` 成功 ≤ 15 min
- [ ] CI 8 项检查（install/lint/format/type/arch/unit/security/healthz）全绿
- [ ] `tach check` 0 违规
- [ ] 覆盖率 ≥ 80%
- [ ] ADR #1, #2, #3 已合并
- [ ] `library_id` 字段贯穿 `Document/Chunk/Entity/Triple`，Pydantic validator 拒绝跨 Library 引用
- [ ] 所有跨 Library 的 Protocol 方法首参为 `library_id`，并预留 `init_library`/`purge_library`
- [ ] README 包含：项目定位、架构图、启动步骤、Library 概念说明、贡献指南链接

### 7.8 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|-------|------|------|
| Tach 配置学习成本高 | 中 | 低 | 先用 import-linter 简化；M1 再切 Tach |
| 数据层容器在 Mac/Linux 差异大 | 低 | 中 | 统一用 amd64 镜像；M1 之前验证多平台 |
| Library 概念被误解为"模块" | 中 | 中 | ADR #3 反复强调"数据维度"；Review checklist 设硬条目 |

---

## 8. M1 — Minimum Viable RAG

**代号**：MVP-RAG
**周期**：3 周
**前置依赖**：M0

### 8.1 目标

**端到端跑通 UC1 最简路径**：上传 PDF → 解析 → 向量索引 → 问答 → 带引用返回。

这一轮不上 KG、不上 Agent，**只求"能问能答能追溯"**。

### 8.2 Scope

**In**：
- **Library CRUD 落地**：
  - Postgres 存 `Library` 元数据；适配器实现 `init_library` / `purge_library`
  - API：`POST /v1/libraries`, `GET /v1/libraries`, `GET /v1/libraries/{id}`, `DELETE /v1/libraries/{id}[?purge=1]`
  - CLI：`rkb library create|list|delete`，全局 `--library` flag；`~/.rkb/config.toml` 默认 Library
- `ingestion`：Nougat 解析器（或 MinerU 适配），Hierarchical Chunker，MinHash 去重
- `embedding`：BGE-M3 adapter（本地）+ OpenAI 3-large adapter（云备选）
- `indexing`：Qdrant VectorIndex adapter，**collection 名 `chunks_<library_id>`**；无图、无 BM25、无 community
- `indexing/service.py`：`VectorRetrievalCoordinator`（单路召回 + 分数阈值；首参 `library_id`）
- `llm`：LLMClient 的 Ollama adapter + OpenAI adapter，Gateway 做 model routing（`prefer_local=True`）
- `retrieval`：最简 `DirectRAGPlanner`（无 Agent loop，直接 search → stuff → answer）
- `orchestration`：`QATask` 模板（ask → retrieve → answer with citation；限定单 Library）
- `apps/api`：`POST /v1/libraries/{id}/ingest`, `POST /v1/libraries/{id}/qa`
- `apps/worker`：订阅 `docs.uploaded` → parse → chunk → embed → upsert（事件 payload 含 library_id）
- `apps/cli`：`rkb --library <id> ingest <path>`, `rkb --library <id> qa <question>`

**Out**：
- KG 抽取 / 图索引
- BM25
- Agent reflection
- Community
- Rerank
- 跨 Library 联合查询

### 8.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D1.1 | Nougat/MinerU 解析 pipeline | 10 篇论文解析无错 |
| D1.2 | Chunker（sentence+hierarchical） | chunk 长度分布符合设计 |
| D1.3 | Qdrant 向量索引（per-Library collection）+ Embedding worker | 1000 chunks 入库 < 5 min |
| D1.4 | LLM Gateway（本地 + 云） | 切换模型无需改业务代码 |
| D1.5 | QA endpoint（library-scoped） | 10 题 smoke test 通过 |
| D1.6 | CLI: `library` / `ingest` / `qa` | 可用；可创建/切换/删除 Library |
| D1.7 | Library 隔离测试 | 两个 Library 分别灌入不同语料；A 的查询不返回 B 的 chunk |

### 8.4 要确定的接口

```python
class Parser(Protocol):
    async def parse(self, file_path: Path) -> ParsedDocument: ...

class Chunker(Protocol):
    def chunk(self, library_id: str, parsed: ParsedDocument) -> list[Chunk]: ...

class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[Vector]: ...   # library 无关
    @property
    def dim(self) -> int: ...

class VectorIndex(Protocol):
    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...
    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Chunk, Vector]],
    ) -> None: ...
    async def search(
        self,
        library_id: str,
        vector: Vector,
        k: int,
        *, filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]: ...

class LibraryRepository(Protocol):
    async def create(self, library: Library) -> None: ...
    async def get(self, library_id: str) -> Library | None: ...
    async def list_all(self) -> list[Library]: ...
    async def soft_delete(self, library_id: str) -> None: ...

class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: ResponseFormat | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse: ...                                  # library 无关

class RetrievalPlanner(Protocol):
    async def plan_and_retrieve(
        self, library_id: str, query: Query, budget: RetrievalBudget
    ) -> RetrievalResult: ...

class QATask:
    async def answer(self, library_id: str, question: str) -> AnsweredQuery: ...
```

**LLM / Embedder 无 library_id**：它们是无状态计算服务，不持久化 Library 数据；Library 隔离仅在持久层生效。

### 8.5 数据模型新增

```python
class ParsedDocument(BaseModel):
    doc: Document                   # 已含 library_id
    sections: list[ParsedSection]

class AnsweredQuery(BaseModel):
    library_id: str
    question: str
    answer: str
    citations: list[Citation]       # [(chunk_id, span)]
    retrieved: list[RetrievedEvidence]
    model: str
    tokens: TokenUsage
    duration_ms: int
```

### 8.6 测试要求

- 单测：所有 adapter 对 Protocol 的契约测试（contract tests）
- 集成测：testcontainers 起 Qdrant，端到端跑 3 篇论文
- E2E：10 题 smoke set，断言引用 non-empty 且每条引用指向存在的 chunk

### 8.7 Exit Criteria

- [ ] 用户用 CLI 创建 Library 并导入 100 篇论文 ≤ 30 min（含解析）
- [ ] 10 题 smoke set 100% 返回答案 + 至少 1 条引用
- [ ] 覆盖率 ≥ 80%
- [ ] `/v1/libraries/{id}/qa` P95 ≤ 15s（本地 Qwen2.5-32B 或 Claude Haiku）
- [ ] LLM Gateway 可一行配置切换 Ollama ↔ OpenAI ↔ Anthropic
- [ ] 多 Library 隔离测试通过：A 的查询不返回 B 的 chunk；purge B 不影响 A
- [ ] `library purge` 后 Qdrant collection / Postgres 行 / MinIO prefix 全部清除（drill 验证）

### 8.8 风险

| 风险 | 缓解 |
|------|------|
| Nougat 在中文公式上漂 | 同时接 MinerU；优先处理目标领域语言 |
| 向量检索对稀有术语召回差 | 记录"失败 case"，为 M2 的 BM25 做数据准备 |
| LLM 响应慢拖跨 UX | Gateway 层加流式 SSE；前端先用 CLI 验证 |

---

## 9. M2 — 知识图谱与混合检索

**代号**：GraphFusion
**周期**：3 周
**前置依赖**：M1

### 9.1 目标

- 从 chunk 抽出 (实体, 关系, 实体) 三元组，构建**带来源**的领域 KG。
- 加入 **BM25** 与 **Rerank**。
- 升级 `RetrievalCoordinator` 为**混合检索 + RRF + Rerank** 三段式。
- 支持 **多跳问答**（至少 2 跳）。

### 9.2 Scope

**In**：
- `structuring`：
  - NER：GLiNER adapter（零样本）
  - RE：LLM-based REBEL-风格 adapter（带 provenance）
  - EntityLinker：字符串 + embedding 双阶段（领域本体绑定 optional）
  - KGWriter：Neo4j（或 Kuzu）adapter，幂等 upsert；**每个 Library 一个 composite database / .kuzu 文件**
  - Schema 管理：YAML 配置 + 运行时校验；**Schema 可 per-Library 覆盖**（`docs/ontology/<library_id>/v1.yaml`）
- `indexing`：
  - GraphIndex Neo4j adapter（1-hop / k-hop / PPR；首参 `library_id`）
  - BM25Index OpenSearch adapter（每 Library 一个 index `bm25_<library_id>`）
  - RerankerService：BGE-reranker-v2 adapter（library 无关）
- `indexing/service.py`：`HybridRetrievalCoordinator`（向量 + 图 + BM25 三路 → RRF → Rerank；首参 `library_id`）
- `retrieval`：`expand_entity` 工具加入 planner（限定 library scope）
- `apps/api`：新增 `GET /v1/libraries/{lib}/entities/{id}/neighborhood`
- 各 GraphIndex / BM25Index 适配器实现 `init_library` / `purge_library`

**Out**：
- Community 检测（M3）
- Self-RAG / CRAG（M4）
- 跨 Library 的 schema 共享/继承机制（v1.1）

### 9.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D2.1 | NER + RE pipeline | 100 chunk 抽取 P ≥ 0.75 / R ≥ 0.65（人工抽检 50 条） |
| D2.2 | 实体消歧 + Neo4j 写入 | 同名实体合并正确率 ≥ 90% |
| D2.3 | 混合检索 + RRF | 多跳 QA Recall@10 比 M1 提升 ≥ 20% |
| D2.4 | Rerank 服务 | 10 题人工评测中 top-3 相关性 ≥ 0.85 |
| D2.5 | Schema YAML + 校验 | 非法关系直接拒 |

### 9.4 数据模型新增

```python
class RetrievedEvidence(BaseModel):
    chunk: Chunk
    score: float
    source: Literal["vector", "graph", "bm25", "community"]
    rank_before_rerank: int
    rank_after_rerank: int

class EntityNeighborhood(BaseModel):
    entity: Entity
    triples: list[Triple]
    depth: int
```

### 9.5 测试要求

- NER/RE 金牌集（人工标注 ≥ 200 三元组），回归测试
- EL 消歧测试：同义词 / 缩写 / 拼写变体
- 多跳 QA 集（≥ 30 题），Recall@10 与 Citation F1 报表
- Rerank before/after 的 nDCG 对比

### 9.6 Exit Criteria

- [ ] 同等语料下，30 题多跳 QA 的 Recall@10 相比 M1 提升 ≥ 20%
- [ ] Citation F1 ≥ 0.80
- [ ] KG 中三元组总数 ≥ 5000（前 200 篇论文后的预期下限）
- [ ] 所有三元组有 ≥ 1 条 provenance chunk_id，且 evidence 与 head/tail 同 library_id
- [ ] `/v1/libraries/{lib}/entities/{id}/neighborhood` P95 ≤ 2s
- [ ] purge Library B 不影响 Library A 的 KG 与 BM25 索引（drill）
- [ ] 覆盖率 ≥ 80%

### 9.7 风险

| 风险 | 缓解 |
|------|------|
| LLM 抽三元组幻觉 | 强制 schema 约束 + provenance 校验（三元组中的 head/tail 必须在 chunk 文本中出现） |
| 消歧误合 | 冲突不合并，保留为多 claim；用户手动确认 |
| Neo4j 单机写入瓶颈 | 批量 MERGE + Graph Data Science plugin；保留切 Kuzu 选项 |

---

## 10. M3 — Community 与全局检索

**代号**：GraphRAG-Global
**周期**：2 周
**前置依赖**：M2

### 10.1 目标

让 Copilot 能回答**"整体性 / 综合性"问题**（"领域主流方法有哪些？""这类工作的共同点？"）—— 不是靠召回具体 chunk，而是靠**社区级摘要**。

### 10.2 Scope

**In**：
- `indexing`：
  - `CommunityDetector`：Leiden 算法（`leidenalg`），支持层级（C0/C1/C2）；**按 Library 独立运行**
  - `CommunitySummarizer`：LLM 对每个社区生成自然语言摘要
  - `CommunityIndex`：摘要文本入向量库（独立 collection `communities_<library_id>`）+ Postgres 存元数据（`library_id` 列）
- `apps/worker`：
  - 定时任务：每日 / 每增量 N 篇触发 `rebuild_community` job（job payload 含 `library_id`）
  - 增量更新策略：仅重算该 Library 内受影响的社区
- `retrieval`：新增 `summarize_community` / `global_search` 工具（首参 `library_id`）
- `orchestration`：`QATask` 增加 **Local vs Global** 路由（简单启发：问句词频 + 问句长度 + 实体命中率）

**Out**：
- Agent 反思（M4）
- 跨 Library 的社区合并/比较（v2）

### 10.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D3.1 | Leiden 社区检测 | 1 万节点图 ≤ 2 min |
| D3.2 | 社区摘要 pipeline | 摘要长度 150–300 字，含 3–5 个代表实体 |
| D3.3 | 增量重建 | 新增 50 篇触发只重算相关社区 |
| D3.4 | Local/Global 路由 | 10 道分类题准确率 ≥ 0.85 |

### 10.4 Exit Criteria

- [ ] 20 题"全局综合题"的答案覆盖度（对比人工综述）≥ 0.70
- [ ] Community rebuild 不阻塞在线查询（独立 worker）；rebuild 只影响目标 Library
- [ ] 每个社区摘要带 `library_id`，指向其成员 entity_id 列表，可追溯
- [ ] 两个 Library 的 community 摘要互不可见（query A 不返回 B 的社区摘要）
- [ ] 覆盖率 ≥ 80%

### 10.5 风险

| 风险 | 缓解 |
|------|------|
| 社区摘要 LLM 成本高 | 增量策略 + 低温度 + 可选小模型（Haiku） |
| Leiden 结果不稳定 | 固定随机种子；保留上版本摘要直到新版 eval 通过 |

---

## 11. M4 — Agentic Retrieval

**代号**：AgentLoop
**周期**：3 周
**前置依赖**：M3（M2 即可开始）

### 11.1 目标

引入**反思与校正**，让检索层在不确定时自主**重检索 / 换策略 / 分解问题**，并在回答前做**引用一致性自检**。

### 11.2 Scope

**In**：
- `retrieval/strategies/`（所有 planner 首参 `library_id`，全程透传）：
  - `ReActPlanner`：基础 ReAct 循环（Thought/Action/Observation）
  - `SelfRAGStyleCritic`：prompt-based 反思（不改 LLM 词表，用 prompt 模拟 4 种 reflection）
  - `CRAGEvaluator`：轻量评估（可用小 LLM 或 cross-encoder 分值阈值）
  - `ToGPlanner`：KG 上 beam search 多跳（深度 ≤ 3，beam ≤ 4），所有图查询限定 library
- `retrieval/rewriter.py`：HyDE / Step-Back / decompose 三策略
- `retrieval/critic.py`：Claim → Evidence 对齐校验（必须验证 evidence chunk 与 query 同 library_id）
- `orchestration`：`QATask` 支持"问题类型路由"（单跳/多跳/全局/定义）
- `llm`：增加 structured output 解析 + 一次降级重试
- 成本/预算控制：`RetrievalBudget` 对象（最大跳数、最大 LLM 调用数、最大 token）；可选 per-Library 上限
- `RetrievalTrace` 含 `library_id`，落 Langfuse 时作为标签

**Out**：
- 多 Agent 对话（推迟至 M5）
- 生成阶段的 beam search
- 跨 Library 的 Agent 协作

### 11.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D4.1 | ReAct 基础循环 | 10 题多跳 smoke pass |
| D4.2 | Self-RAG 风格 critic | Citation F1 较 M3 提升 ≥ 5 pp |
| D4.3 | CRAG 评估器 + 重检索 | "检索失败"场景的兜底率 ≥ 60% |
| D4.4 | ToG beam search | 3 跳问题成功率 ≥ 0.55 |
| D4.5 | Query rewriter | 长尾 query 的 Recall@10 提升 ≥ 10% |

### 11.4 数据模型新增

```python
class RetrievalStep(BaseModel):
    step_idx: int
    thought: str
    action: str
    action_input: dict[str, object]
    observation: str
    cost: StepCost

class RetrievalTrace(BaseModel):
    library_id: str                          # 全程绑定，便于按 Library 分析
    steps: list[RetrievalStep]
    final_evidence: list[RetrievedEvidence]  # 每条 evidence 的 library_id 必须一致
    budget_used: BudgetUsage
    terminated_reason: Literal["answer_ready", "budget_exceeded", "error"]

class RetrievalBudget(BaseModel):
    max_steps: int = 8
    max_llm_calls: int = 20
    max_tokens: int = 32_000
    timeout_s: float = 60.0
```

### 11.5 Exit Criteria

- [ ] 30 题多跳 QA 的 Citation F1 ≥ 0.85
- [ ] 可切换 planner（env var 或 per-request），对比报告入 Grafana
- [ ] Trace 全量落 Langfuse，可回放
- [ ] 覆盖率 ≥ 80%

### 11.6 风险

| 风险 | 缓解 |
|------|------|
| Agent 无限循环 | 硬性 Budget + 超时 |
| Planner 间质量回退 | A/B 评测强制门槛，新 planner 不达标不合入 |
| LLM 成本飙升 | Gateway 层 per-request cost cap；超限返回部分答案 |

---

## 12. M5 — 科研任务模板

**代号**：ScientificTasks
**周期**：3 周
**前置依赖**：M4

### 12.1 目标

在扎实的检索基础上，交付科研工作流的**三类任务模板**：综述、跨文献推理、假设生成（基础版）。

### 12.2 Scope

**In**：
- `orchestration/tasks/`（所有任务限定单 Library；TaskRunner 首参 `library_id`）：
  - `ReviewGenerationTask`：主题 → 全局召回 → 子主题切分（LLM）→ 每子主题 local search → 拼接大纲 → 写作 → 引用核对。**用户可配置：年份范围、目标字数（1500/3000/5000）、引用风格（编号 / 作者-年份）、可选手动子主题 chip**。
  - `CrossPaperReasoningTask`：问题分解 → 并行检索 → ToG 在 KG 上跑 meta-path → 聚合 + 证据回填（meta-path 不出 Library）；输出**结构化 path**（`list[(entity, relation, entity)]`），供前端可视化。
  - `HypothesisTask`（基础版）：实体对输入 → 路径挖掘（最短路径/常见 meta-path）→ LLM 生成解释 → 引用反驳。**每条假设携带三维评分**：
    - `novelty ∈ [0,1]`：与已知文献结论的重叠度（embedding 距离 + 引用计数反向）
    - `confidence ∈ [0,1]`：KG 路径数 × 路径置信度的几何均值
    - `verifiability ∈ [0,1]`：可被实验或文献交叉验证的程度（启发式：路径上是否含 Method / Dataset 节点）
  - 排序按 `novelty × confidence` 降序。
- 任务通用框架：
  - `TaskRunner` 接口：`run(library_id, task_input, *, dry_run, cost_estimate, stream_progress)`
  - Temporal 或 Arq 长任务封装（综述可能跑 5–15 min）；任务记录 per-Library 预算与成本
  - **后台运行**：所有长任务支持「Run in background」—— 任务进入队列后，前端可关闭页面，完成后通过顶栏 Notify 通知用户回访任务页查看结果；任务支持断点续跑。
  - **进度事件**：SSE 吐出结构化阶段事件（`stage_started` / `stage_progress` / `stage_completed` / `task_completed`），前端据此渲染 pipeline tree。
- `apps/api`：`POST /v1/libraries/{lib}/review`, `.../reason`, `.../hypothesize`（均支持 SSE 流式）；`GET /v1/libraries/{lib}/tasks/{task_id}` 查询任务状态。

**Out**：
- 完整 AI co-scientist 式 Generate-Debate-Evolve（v2+）
- 湿实验集成
- 跨 Library 综述/对比（v2）

### 12.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D5.1 | 综述生成任务 | 5 个主题人工评分 ≥ 3.5 / 5.0（覆盖度、引用、可读性三项）；引用风格切换可用 |
| D5.2 | 跨文献推理任务 | 20 题 3 跳问题的答案正确率 ≥ 0.60；返回结构化 path 可前端可视化 |
| D5.3 | 假设生成（基础） | 5 个实体对各产出 ≥ 3 个合理假设；每条带 novelty/confidence/verifiability 三维评分 |
| D5.4 | 长任务 SSE 进度 | 前端可实时看到"正在召回第 3 子主题..."；阶段事件结构化 |
| D5.5 | 后台任务 | "Run in background" 后关闭页面再回访任务页可恢复进度；通知中心收到完成事件 |

### 12.4 Exit Criteria

- [ ] 综述 3000 字 ≤ 10 min，引用正确率 ≥ 0.85
- [ ] 跨文献推理的 path 可在 KG 浏览器中查看
- [ ] 每个任务有预估成本 API
- [ ] 覆盖率 ≥ 80%

### 12.5 风险

| 风险 | 缓解 |
|------|------|
| 综述长文引用漂移 | 写完后独立 critic 再查一遍 Claim-Evidence |
| 假设合理但无据 | 要求每条假设至少 2 条 KG 路径作证据 |
| 长任务中断后状态丢失 | Arq job + outbox；支持断点续跑 |

---

## 13. M6 — 评测与可观测

**代号**：QualityLoop
**周期**：2 周
**前置依赖**：M5（可与 M5 部分并行）

### 13.1 目标

建立**持续评测 + 全链路可观测**，让每次改动都能看见质量变化。

### 13.2 Scope

**In**：
- `evaluation`：
  - Ragas runner：Faithfulness / Answer Relevancy / Context Precision & Recall
  - Custom metrics：Citation F1、Recall@k、P95 latency
  - **金牌评测集 per-Library** 组织（`data/libraries/<library_id>/evals/qa.smoke.v1.yaml` 等）：
    - 评测集与 Library 数据同目录（`data/libraries/<lib>/evals/`），便于按 Library 管理
    - 每个 Library 至少有 `qa.smoke.v1`（10 题）+ `qa.multihop.v1`（30 题）+ `review.v1`（5 主题）
    - 评测集支持自动生成：灌入语料后 `rkb eval generate --library <id>` 用 LLM 从 chunk 生成 QA 对（draft），人工审核后标记 `human_validated: true`
    - 主 Library（首个领域）作为 PR 阻塞门槛；其他 Library nightly 跑
  - LLM-as-Judge（G-Eval 风格）用于子观性问题
  - 评测样本 schema 含 `library_id`，确保问题在该 Library 内可答
- 可观测：
  - OpenTelemetry trace 覆盖 L1–L5 关键 span（含 `library_id` 标签）
  - Langfuse 自托管，LLM 全量 trace（按 Library 分项目或加 tag）
  - Grafana dashboard：VAR 趋势 / Citation F1 / P95 / cost；**Library 维度过滤器**
  - Alerting：VAR 周环比下跌 > 5 pp 告警（按 Library 分别告警）
- 评测 CI：PR 上跑主 Library 的 smoke set，结果贴回 PR 评论

**Out**：
- 人类反馈收集（v1.1）

### 13.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D6.1 | Ragas 集成 + 5 指标报表 | `make eval` 输出 markdown |
| D6.2 | Langfuse 本地部署 | 任一 QA 可在 UI 回放 |
| D6.3 | Grafana dashboard | 3 面板齐全 |
| D6.4 | PR 自动评测 | smoke set 延迟 ≤ 3 min |

### 13.4 Exit Criteria

- [ ] 每次 PR 自动跑 smoke set，结果贴在 PR
- [ ] v1.0 前的 3 个 release candidate 都在 dashboard 留痕
- [ ] Trace 采样率 100%（开发）/ 10%（生产）
- [ ] 有 runbook：如何看 dashboard、如何查一条失败 QA

### 13.5 风险

| 风险 | 缓解 |
|------|------|
| 评测集过小导致指标噪音 | 目标：v1.0 前 ≥ 100 题；每月扩充 |
| LLM-Judge 不稳定 | 双 LLM 独立打分取均值；定期人工校准 |

---

## 14. M7 — 硬化与用户体验

**代号**：Hardening
**周期**：3 周
**前置依赖**：M6

### 14.1 目标

把一个"开发者自己能用"的系统，打磨成"研究组里的非工程师也能日常用"的工具。

### 14.2 Scope

**In**：
- **Web UI**（**Vue 3 + Vite + TypeScript strict**；详见 `docs/FRONTEND_CODING_STANDARDS.md` 与 `docs/UI_UX.md`）：

  **技术栈与契约**：
  - Vue 3.4+ Composition API + `<script setup>` / Pinia / Vue Router 4 / Naive UI / UnoCSS / ECharts / Cytoscape.js
  - `openapi-typescript` 由后端 `/openapi.json` 自动生成 DTO；前端不手写类型
  - 所有 Library-scoped 页面 URL 携带 `:libraryId`（与后端 per-Library 物理隔离对偶）
  - 切库 = 路由跳转 + 自动清空相关 store

  **顶栏**（全局可见）：
  - Logo + LibrarySwitcher（含搜索 / 最近 / 固定置顶 / "+ New Library"）
  - Breadcrumb
  - **`⌘K` 命令面板 Overlay**：全局唤起，搜索 Library / 文档 / 实体 / 任务 / 设置；支持快速跳转与命令执行
  - Notify 中心（任务完成、告警、配额提醒等）
  - **i18n 切换**（zh-CN ↔ en-US，`vue-i18n`，CI 校验 key 集合一致）+ 用户菜单（Avatar）

  **核心页面**：
  - **Library Dashboard** (`/libraries`)：跨库 Stats 卡片（文档/chunk/实体/三元组/社区/摘要新鲜度，**ECharts**）；Library 状态徽章三态 `Healthy / Indexing / Stale community`；Quality KPI 总览面板（VAR / Citation F1 / P95 / cost），可按 Library 过滤
  - **LibraryCreateModal**：建库向导（slug / 名称 / 描述 / 主语言 / 默认 schema）；slug 必须满足 `^[a-z][a-z0-9-]{2,30}$`
  - **DeleteConfirmModal**：删除 Library 时强制输入完整 slug 才能确认；删除后自动跳回 `/libraries`
  - **Chat / QA** (`/lib/:id/chat`)：SSE 流式（`useSSE` composable）；引用 chip 点击跳章节（只信任后端 `citations[]`）；**reasoning trace 内联展开**（默认收起，展开显示 RetrievalStep 列表 + Langfuse 直链）；**斜杠命令** `/review` / `/reason` / `/hypothesize` / `/clear` / `/rerank-on`，回车后跳对应任务页或就地配置；**多轮会话列表**（侧栏顶部，最近 N 条会话，点击恢复上下文）；**Empty States**：0 命中 → 显式空态卡，禁止 LLM 假装回答
  - **KG Browser** (`/lib/:id/kg`)：**Cytoscape.js** 力导向，仅显示当前 Library；默认 top-50 邻居 + 6 类型过滤 chip + 深度滑杆（1-3 hop）+ confidence 阈值；节点详情抽屉
  - **Documents** (`/lib/:id/docs`)：拖拽上传单 PDF / ZIP / 文件夹；解析与索引进度可视化（Queued / Parsing / Indexing / Ready / Failed 五态）；失败 → popover 显示错误详情 + Retry 按钮；**DocumentDetailDrawer** 显示 PDF preview + 章节大纲 + chunk 列表
  - **Tasks** (`/lib/:id/{review,reason,hypothesize}`)：配置 → cost 估算 → Run / Run in background；任务进行中页含 pipeline tree + 流式输出 + 实时引用清单 + cost / token 仪表；任务可后台运行，完成后通过顶栏 Notify 通知
  - **Eval Dashboard** (`/lib/:id/eval`)：4 张 KPI 卡（VAR / Citation F1 / P95 / cost）+ 30 天趋势 + 失败 case 表 + Library 过滤器 + **VAR 周环比下跌 > 5pp 顶部告警 banner**
  - **Settings** (`/lib/:id/settings` + `/settings`)：per-Library 配置覆盖（LLM Router / Embedder / 检索预算 / 每日成本上限）；Schema YAML 编辑器；Export / Import / Purge（Purge 复用 DeleteConfirmModal 模式）

  **跨页面体验规范**：
  - 所有引用 chip 用统一 `info` 色板（与 brand 区隔）
  - 长任务一律 first-class：可后台、可恢复、有结构化进度
  - 所有 Empty State / Error State / Loading State（skeleton ≥ 800ms 才显示）有显式设计
  - 焦点环 / 键盘可达 / a11y AA 全程满足

  **测试**：
  - Vitest 单测 ≥ 80%
  - Playwright 5 条 E2E：建库 → 上传 → 提问 → 综述 → 评测面板访问

- **认证**（轻量）：单机 JWT 或 Keycloak（可选）
- **错误恢复**：
  - 所有长任务幂等
  - 摄取失败可从断点续跑
  - API 统一错误信封 + 错误码枚举
- **限流 / 配额**：Redis token bucket（防个人滥用）；**per-Library 每日成本上限**（settings 可配，超限阻断新任务并提示用户）
- **文档完善**：
  - User Guide（给研究者，含 Library 概念与最佳实践）
  - Operator Runbook（给自己/同事）
  - API Reference（OpenAPI 导出）
  - 3 个示例 notebook（`docs/examples/`，演示创建 Library → 灌入 → 提问）
- **数据备份**（per-Library 粒度）：
  - `rkb library export <id> --out <path>`：导出该 Library 的 Postgres 行 / Qdrant collection / Neo4j DB / MinIO prefix（含索引数据）
  - `rkb library import <path> --as <id>`：跨机器迁移
  - 全局 snapshot 脚本：备份所有 Library

**Out**：
- 移动端 / iOS / Android
- 跨 Library 联合**数据查询**（v1 仅允许 L5 编排层组合**只读元视图**，详见 §16.6）

### 14.3 关键交付

| # | 交付物 | 验收 |
|---|-------|------|
| D7.1 | Web UI v1（8 屏 + 4 Modal/Drawer） | Onboarding / LibraryDashboard / Chat / KG / Review / Documents / Reason+Hypothesize / Eval+Settings 全部按 `docs/UI_UX.md` 落地 |
| D7.2 | KG 浏览器 | 实体点击展开邻域可视；只显示当前 Library；6 类型过滤可用 |
| D7.3 | User Guide | 新用户 15 min 内完成首次 QA（含 Library 创建） |
| D7.4 | per-Library 导出/导入 + 全局备份 | 本地 drill 成功恢复；可迁移到另一台机器；导出含 Qdrant/Neo4j/BM25 索引数据 |
| D7.5 | 后台任务 + 通知 | Review/Reason/Hypothesize 可后台运行；完成时顶栏通知；任务页可恢复进度 |
| D7.6 | per-Library 配置覆盖 | LLM 路由 / Embedder / 检索预算 / 每日成本上限可在单 Library 内独立配置 |
| D7.7 | 双语 UI | zh-CN + en-US 顶栏切换；CI 校验 key 完整性 |
| D7.8 | ⌘K 命令面板 | 全局快捷键唤起；可搜索跳转 Library / 文档 / 实体 / 任务 |

### 14.4 Exit Criteria

- [ ] 5 位目标用户 α 测试完成：VAR ≥ 70%
- [ ] 运维 Runbook 含 10 个常见故障的排查步骤
- [ ] 回归测试：v1.0 发布前 100 题完整 eval 通过
- [ ] 无 P0/P1 bug 未修

### 14.5 风险

| 风险 | 缓解 |
|------|------|
| UI 拖慢主线 | Vue 3 + 成熟生态（Naive UI / UnoCSS）+ openapi-typescript 自动契约，避免手写 DTO 漂移 |
| KG 可视化大图卡 | 默认只渲染 top-N 邻居；提供过滤；Cytoscape 路由懒加载 |
| 前端类型与后端契约漂移 | CI 强制 `pnpm gen:api && git diff --exit-code`；DTO 全部来自 OpenAPI |
| 切库残留导致跨 Library 数据泄漏 | URL 强制 `:libraryId`；切库 watcher 清空 qaStore/kgStore |

---

## 15. M8 — 面向未来的扩展

**代号**：FutureProof
**周期**：持续（v1.0 后）
**前置依赖**：v1.0 发布

### 15.1 目标

**不立刻做，但随时能做**：把未来 6–12 个月最可能的演进方向铺好路。

### 15.2 Scope（候选池，按优先级选做）

- **性能基线**：
  - 定义基线套件（摄取 / 索引 / QA / 综述）
  - 每周跑一次，性能退步自动告警
- **抽服务预演**：
  - 选一个最可能外抽的 package（很可能是 `llm` 或 `embedding`）做"假抽服务"：增加远程 adapter 但仍同进程跑
  - ADR 记录抽服务触发条件
- **v2 预研**：
  - 完整 AI co-scientist 式多 Agent
  - KG embedding 路径挖掘（TransE / RotatE）做高级假设
  - Deep Research 风格自动综述
  - **跨 Library 联合数据查询**（差异分析 / 共性发现，覆盖 L1-L4 数据层；v1 已支持 L5 编排层只读元视图）
  - 本地多租户与协作
- **生态集成**：
  - Zotero / Obsidian 插件
  - VS Code extension（在代码上下文问 KB）

> **注**：原 v2 候选项「Library 配置覆盖体系（per-Library embedder / LLM / 语言）」已在 M7 v1 落地（详见 §14.2 Settings 部分），从本节移除。

### 15.3 产出（持续）

- ADR #N：每个架构决策留痕
- Perf report（每月一份）
- v2 PRD（目标：v1.0 后 3 个月内完成）

### 15.4 Exit Criteria

本里程碑无硬 Exit —— 每季度滚动评审。

---

## 16. 横切关注点

贯穿所有里程碑，不单列里程碑但每阶段都要"维持":

### 16.1 文档同步

- 架构级决策 → ADR（不写不合并）
- 运维动作 → Runbook
- 用户可见变更 → CHANGELOG.md
- 每里程碑末尾更新 README 的"能力矩阵"

### 16.2 评测体系演进

- M2 起，每里程碑新增 ≥ 20 题评测集
- 评测集按任务类型分文件管理
- 金牌集（高置信人工标注）与银牌集（LLM-Judge）分桶

### 16.3 性能基线

| 阶段 | 采集项 |
|------|-------|
| M1 起 | 摄取吞吐 / QA P95 / 模型 token |
| M3 起 | Community rebuild 耗时 |
| M4 起 | Agent 平均步数 / 平均调用成本 |
| M6 起 | 各项持续上 Grafana |

### 16.4 安全与合规

- 摄取数据的版权合规（用户自担）；系统仅支持用户合法持有的文献
- 密钥不入库；gitleaks 全程
- M7 前完成一次 `security-review` agent 审查
- 本地部署优先，保证数据不出本机/机房

### 16.5 技术债管理

- 每周一条"技术债卡"：在哪、为什么欠、何时还、阻塞了什么
- 每里程碑末尾有 1 天 "debt-repay"

### 16.6 Library 维度纪律

贯穿所有里程碑必须坚持的硬规矩（详见 `CODING_STANDARDS §6.5 / §12.5 / §13.5`）：

- Library 是数据维度，**不开 package**、**不进分层**
- 跨 Library 的领域模型首字段是 `library_id`
- **L1–L4（数据层 / 检索层）**：Protocol 方法跨 Library 时首参 `library_id`，**不接受 `library_ids: list`**；适配器按 `library_id` 物理隔离（collection / database / index / prefix）
- **L5（编排层）例外**：允许组合**只读元视图**，例如：
  - 跨 Library 活动流（每条记录仍带 `library_id`，列表是 client-side / orchestration-side 聚合）
  - Library 列表与 Stats 总览
  - Eval Dashboard 的 Library 过滤器
  - ⌘K 命令面板的全局搜索（Library / 任务 / 实体名）

  这些视图必须**只读**、**用户身份范围内**，不得从中触发跨 Library 的数据查询或写入。
- 评测、日志、trace、指标都按 `library_id` 切分
- 每次新增模型/接口时审查："这个东西是 library 无关（如 LLM/Embedder 计算）还是 library 内（数据相关）？是 L1–L4 数据访问还是 L5 编排聚合？"

### 16.7 Library 状态枚举

每个 Library 有以下三态，用于 UI 徽章与告警：

| 状态 | 触发条件 | UI 颜色 |
|---|---|---|
| `Healthy` | 索引齐全 + community 摘要新鲜（< 7 天） + 无失败任务 | success（绿） |
| `Indexing` | 当前有摄取 / KG 抽取 / community rebuild 任务在跑 | brand（蓝） |
| `Stale community` | 社区摘要超 7 天未更新且新增文档 ≥ 50 篇 | warning（琥珀） |

状态由 `library_admin` 周期性巡检写入 Postgres `libraries.status` 字段。

---

## 17. 风险登记册

| ID | 风险 | 概率 | 影响 | 缓解 | 负责里程碑 |
|----|------|------|------|------|-----------|
| R01 | LLM 成本失控 | 中 | 高 | Gateway 层 per-request cap + 小模型优先路由 | M1 / M4 |
| R02 | PDF 解析质量拖累下游 | 中 | 高 | 多解析器并存 + 人工抽检 | M1 |
| R03 | KG 抽取幻觉 | 高 | 高 | Schema 约束 + provenance 强校验 | M2 |
| R04 | 评测集过小导致指标噪音 | 中 | 中 | 每月扩充；不同任务分桶 | M6 |
| R05 | 个人项目倦怠 | 中 | 高 | 里程碑切小；每周可见进展；Demo 驱动 | 全程 |
| R06 | 依赖库重大升级破坏 | 低 | 中 | 锁依赖 + 月度升级演练 | 全程 |
| R07 | 硬件瓶颈（单机 GPU） | 中 | 中 | 可切 API 模型 fallback；M8 抽服务 | M1 / M8 |
| R08 | Schema 提前冻结不合理 | 中 | 中 | Bottom-up 诱导 + evolution 窗口 | M2 |
| R09 | Neo4j/Qdrant 数据丢失 | 低 | 高 | M7 建备份脚本 + 周期恢复演练 | M7 |
| R10 | 用户期望错配（把它当 ChatGPT） | 中 | 中 | User Guide 明确定位；UI 展示引用强调可追溯 | M7 |
| R11 | Library 数据混淆（A 的 chunk 出现在 B 的回答） | 低 | 高 | Pydantic validator 拒跨 Library 引用；适配器物理隔离；M1 起每里程碑回归测 | M0 / M1 / 全程 |
| R12 | Library 概念被误用为"模块/服务" | 中 | 中 | ADR #3 反复声明；Code Review checklist 设硬条目；本规则进 onboarding | 全程 |
| R13 | Library 多到管理混乱（用户开 N 个） | 中 | 低 | UI Stats 面板 + 软删保留 30 天；定期清理空 Library 提示 | M7 |

---

## 18. 发布与版本策略

### 18.1 版本号

`MAJOR.MINOR.PATCH`

- v0.1.0 = M0 完成
- v0.2.0 = M1 完成
- ...
- **v1.0.0** = M7 完成 + α 测试通过
- v2.0.0 = v1 之上的重大架构演进（M8 预研后决定）

### 18.2 Release Train

- 每里程碑 → 一个 minor release
- PATCH：bug 修复 / 小优化
- Release 前必须通过：
  - 完整 eval（smoke + multihop + review）
  - 回归测试
  - CHANGELOG 更新
  - Runbook 同步

### 18.3 α / β / GA

| 阶段 | 版本 | 对象 | 标准 |
|------|------|------|------|
| 内部 α | v0.7 (M6) | 开发者自用 | 功能完整 |
| 外部 α | v0.9 (M7) | 3–5 位真用户 | VAR ≥ 0.60 |
| β | v1.0-rc | 10–30 位用户 | VAR ≥ 0.70 |
| GA | v1.0 | 公开 | VAR ≥ 0.75；无 P0/P1 |

---

## 附录 A — 里程碑甘特草图

```
Week:   1  2 | 3  4  5 | 6  7  8 | 9 10 |11 12 13|14 15 16|17 18|19 20 21|
M0 Foundation [====]
M1 MVP-RAG          [=========]
M2 GraphFusion                 [=========]
M3 Community                            [======]
M4 AgentLoop                            [=========]   (与 M3 末并行)
M5 Tasks                                         [=========]
M6 QualityLoop                                            [======]
M7 Hardening                                                     [=========]
M8 FutureProof                                                            [===>持续]
```

（宽度仅示意；部分里程碑可重叠开工。）

---

## 附录 B — 交付物清单总表

| 里程碑 | 代码 | 文档 | 数据/评测 | 基础设施 | Library 相关 |
|-------|------|------|----------|---------|------|
| M0 | 仓库骨架 / Protocol 占位 / healthz | README / ADR #1-3 | — | docker-compose / CI | `Library` 模型 + `library_id` 贯穿；ADR #3 |
| M1 | ingest/embed/vector/llm/qa | API doc v1 | smoke QA (10) | Qdrant + Ollama | Library CRUD API + CLI；per-Library Qdrant collection；隔离测试 |
| M2 | ner/re/el/graph/bm25/rerank | ADR #4 schema / ADR #5 reranker | multihop QA (30) / triple 金牌集 | Neo4j + OpenSearch | per-Library Neo4j composite DB / BM25 index；schema YAML per-Library |
| M3 | leiden/community/global search | ADR #6 community | global QA (20) | Community collection | per-Library community 计算与缓存 |
| M4 | react/self-rag/crag/tog/rewriter/critic | ADR #7 agent | multi-hop expanded (50) | Langfuse(部分) | RetrievalTrace 含 library_id；Langfuse 按 library 打标 |
| M5 | review/reason/hypo tasks | User Guide（初稿） | review (5) / reason (20) / hypo (5) | Arq 长任务 | TaskRunner library-scoped；任务预算 per-Library |
| M6 | ragas runner / metrics | Runbook / dashboard guide | 金牌集 ≥ 100（per-Library 分桶） | Langfuse / Grafana / Alerting | Dashboard library 过滤；告警按 library 分别 |
| M7 | web UI / auth / rate-limit / backup | User Guide（正式）/ Operator Runbook / OpenAPI | α 测试报告 | 备份脚本 | UI Library 切换器；per-Library export/import |
| M8 | perf / remote-adapter / v2 POC | v2 PRD / ADR #N | Perf baseline | — | 跨 Library 联合查询调研 |

---

## 最后

本文件与 `CODING_STANDARDS.md` 是项目**两根支柱**：一根管"做什么、什么时候做完"，一根管"怎么做才不后悔"。

- **任何开发动作都要能对应到某个里程碑的某条 Exit Criteria**。
- **任何范围变更都要先改本文件**（PR 中），再动代码。
- **任何里程碑延期超过 30% 必须复盘**，写短 postmortem 进 `docs/postmortem/`。

**原则**：里程碑切小 > 切大；纵向切 > 横向切；可展示 > 内部完备。
