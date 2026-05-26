# RAG-KG Copilot — 项目总览

> 本文档是「重新进入项目」的单一入口。把仓库里散布在 `PRD.md` / `CODING_STANDARDS.md` / `UI_UX.md` / `API_REFERENCE.md` / `EVAL_ARCHITECTURE.md` / `USER_GUIDE.md` / 23 个 ADR / README 里的核心信息，按主题汇总到一张文档里。详细技术细节仍以各原文档为准；此文档作为**地图**与**记忆点**。

**文档状态**：v1.0 / 综述（基于 M0–M8 已完成的代码与文档）
**最后更新**：2026-05-17
**配套文档**：`docs/PRD.md` · `docs/CODING_STANDARDS.md` · `docs/UI_UX.md` · `docs/API_REFERENCE.md` · `docs/EVAL_ARCHITECTURE.md` · `docs/USER_GUIDE.md` · `docs/FRONTEND_DESIGN_SPEC.md` · `docs/FRONTEND_RULES.md` · `docs/UI_PROMPTS.md` · `docs/adr/0001 ~ 0023`

---

## 目录

1. [一句话定位](#1-一句话定位)
2. [愿景与解决的问题](#2-愿景与解决的问题)
3. [主要思想](#3-主要思想)
4. [核心概念：Library 是数据分区](#4-核心概念library-是数据分区)
5. [五层模块化单体架构](#5-五层模块化单体架构)
6. [数据层（六种存储后端各自承担什么）](#6-数据层六种存储后端各自承担什么)
7. [检索栈：四索引 + RRF + Rerank + Agent](#7-检索栈四索引--rrf--rerank--agent)
8. [知识图谱构建与 Community](#8-知识图谱构建与-community)
9. [Agent 编排与四种 Planner](#9-agent-编排与四种-planner)
10. [五大科研任务（UC1–UC5）](#10-五大科研任务uc1uc5)
11. [评测体系：8 指标 + 三种执行模式](#11-评测体系8-指标--三种执行模式)
12. [M0–M8 里程碑全景](#12-m0m8-里程碑全景)
13. [23 个 ADR 一句话索引](#13-23-个-adr-一句话索引)
14. [前端：Vue 3 + Cobalt Lab 设计系统](#14-前端vue-3--cobalt-lab-设计系统)
15. [HTTP API 全景](#15-http-api-全景)
16. [CLI（rkb）命令全景](#16-clirkb命令全景)
17. [数据组织：data/libraries/](#17-数据组织datalibraries)
18. [配置 / 安全 / i18n / 可观测性 / 成本控制](#18-配置--安全--i18n--可观测性--成本控制)
19. [部署：Docker Compose + Makefile](#19-部署docker-compose--makefile)
20. [非目标 / 已知边界 / v1.1+ 计划](#20-非目标--已知边界--v11-计划)
21. [入门路径与"重新进入项目"的快速通道](#21-入门路径与重新进入项目的快速通道)

---

## 1. 一句话定位

**RAG-KG Copilot** 是一个**面向科研的、本地自托管的「稠密知识库 + 知识图谱」Copilot**，让博士 / 博后 / 小型课题组也能像团队那样跟住并深耕一个研究方向。

- **项目代号**：`rag-kg-copilot`
- **当前状态**：M0–M8 全部完成（评测系统 + 上下文管理 + Vue 3 前端均已上线）
- **目标用户**：博士 / 博后（深耕单一子方向）+ 3–10 人小型课题组
- **非用户**：通用聊天用户、企业多租户 SaaS 用户

---

## 2. 愿景与解决的问题

### 2.1 一句话愿景

> **让一个人，也能像一支团队那样，跟上并深耕一个科研方向。**

### 2.2 解决的四个核心问题（PRD §1.2）

| # | 痛点 | 现状 |
|---|------|------|
| 1 | **文献洪流** | 单一子方向每月新增数百篇，研究者无法跟读 |
| 2 | **LLM 幻觉** | 普通 ChatGPT 类工具答题无可追溯引用，无法用于严肃科研 |
| 3 | **检索失效** | 向量 RAG 在多跳、跨文献、需要结构化关系的问题上失效 |
| 4 | **工具割裂** | PaperQA / Elicit / ResearchRabbit 各解其一环，缺乏统一的"稠密本地 KB + Agent"底座 |

### 2.3 v1.0 北极星指标

| 指标 | 目标 | 含义 |
|------|------|------|
| **VAR（Valid Answer Rate）** | **≥ 75%** | 用户提问 → 收到带引用答案 → 标记"有用 + 引用正确"的比例。在 100 题金牌评测集上 |
| Citation F1 | ≥ 0.85 | claim-evidence 对齐度 |
| Recall@10（多跳） | ≥ 0.70 | 多跳 QA 召回 |
| P95 延迟 | ≤ 20s | 用户可感知 |
| 每题成本 | ≤ $0.10 | LLM 成本可控 |
| 摄取吞吐 | ≥ 50 篇/小时 | 单机 GPU |
| 测试覆盖率 | ≥ 80% | 工程质量 |
| tach 违规数 | = 0 | 架构合规 |

---

## 3. 主要思想

把**三件事合一**：

```
知识图谱   ← 论文之间关系的结构化记忆
   +
多索引检索  ← 稠密性保障（向量 + BM25 + 社区摘要 + 图）
   +
Agent 编排  ← 任务闭环的大脑
   ↓
面向科研的 Copilot
```

> **底层假设**：稠密但小的本地知识库 + 三类检索通道 + 反思型 Agent，可以在单一科研方向上超过通用大模型的可靠性。

### 3.1 六条设计原则（UI_UX §0 + CODING_STANDARDS 序言）

| 原则 | 含义 |
|---|---|
| **Citation-first** | 任何 LLM 输出都以引用 chip 出现，点击即跳证据；前端会过滤掉不在 `citations[]` 里的 `[id]` |
| **Library-aware** | URL/状态/视觉提示始终告诉用户「我现在在哪个 Library」 |
| **Progressive Disclosure** | 默认极简界面，高级旋钮（reranker / planner / budget）折叠在二级菜单 |
| **Long-task First-class** | 综述/批量摄取等长任务有显式进度面板，可后台、可恢复 |
| **Trust through Trace** | 任何答案都能展开"它是怎么得来的"（检索步骤、命中分数） |
| **Keyboard-native** | 所有主流程支持 `⌘K` 命令面板与快捷键 |

### 3.2 工程层底层准则

> 接口先于实现；模块化先于优化；可测试先于便捷。

---

## 4. 核心概念：Library 是数据分区

### 4.1 定义

**Library**（资料库）= 一个研究方向的完全独立的资料宇宙。例：

- `graphrag-survey`（GraphRAG 综述方向）
- `drug-target-discovery`（药物靶点发现方向）
- `neuro-causal-inference`（神经因果推断方向）

**Library ID** 是 slug，正则 `^[a-z][a-z0-9-]{2,30}$`，3–30 字符，全小写 + 数字 + 连字符。

### 4.2 心智模型（CODING_STANDARDS §6.5）

> **系统不知道有几个 Library；系统只知道每条数据有 `library_id`，所有读写都按它过滤/路由。**

### 4.3 Library ≠ 多租户（ADR #3 强调）

| 维度 | Library | 多租户 |
|------|---------|-------|
| 隔离对象 | **数据** | 身份 / 权限 / 计费 |
| 是否进入架构层 | **不**进入；不开 package | 进入；通常有 `tenant_service/` |
| 用户身份 | v1 单用户 | 多用户 |
| 跨界查询 | v1 禁止（v2+ 候选） | 视权限而定 |

### 4.4 跨 Library 硬规矩（CODING_STANDARDS §6.5 / §12.5 / §13.5）

1. **不开新 package**：不写 `packages/library/`。Library 是数据维度的命名空间，不是行为维度的模块。
2. **所有跨 Library 模型首字段是 `library_id: str`**：`Document` / `Chunk` / `Entity` / `Triple` / `RetrievedEvidence` / `Citation` / `RetrievalTrace` / 评测样本……
3. **唯一性约束 `(library_id, *)`**：`chunk_id` 在单 Library 内唯一即可；跨 Library 引用视为非法（Pydantic validator 拒）。
4. **Protocol 方法跨 Library 时首参 `library_id`，不接受 `library_ids: list`**。L5 编排层例外（允许只读元视图聚合）。
5. **每个适配器实现 `init_library` / `purge_library`**，由薄 helper `packages/core/library_admin.py` 编排。

### 4.5 Library 三态（PRD §16.7）

| 状态 | 触发条件 | UI 颜色 |
|---|---|---|
| `Healthy` | 索引齐全 + community 摘要新鲜（< 7 天）+ 无失败任务 | success（绿） |
| `Indexing` | 当前有摄取 / KG 抽取 / community rebuild 任务在跑 | brand（蓝） |
| `Stale community` | 社区摘要超 7 天未更新且新增文档 ≥ 50 篇 | warning（琥珀） |

---

## 5. 五层模块化单体架构

### 5.1 分层图（CODING_STANDARDS §3.1 / README）

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

**Library 维度（正交于上图）**：所有 L1–L5 操作都按 `library_id` 物理分区。架构层不感知 Library 存在，只把 `library_id` 当成"必填的分区键"透传到适配器。

### 5.2 每层职责

| 层 | 包 | 职责 | 关键 Protocol |
|---|----|------|--------------|
| **apps** | `apps/api`, `apps/worker`, `apps/cli` | 进程入口（HTTP / 异步任务 / CLI） | — |
| **L5** orchestration | `packages/orchestration/` | 科研任务模板（QA / Review / Reason / Hypothesis） | `QATask`, `ReviewTask`, `CrossPaperReasoningTask`, `HypothesisTask` |
| **L4** retrieval | `packages/retrieval/` | Agent 检索规划 / Planner / Critic / Rewriter | `RetrievalPlanner` |
| **L3** indexing | `packages/indexing/` | 四索引 + 混合协调 | `VectorIndex` / `GraphIndex` / `BM25Index` / `CommunityIndex` / `RerankerService` / `HybridRetrievalCoordinator` |
| **L2** structuring | `packages/structuring/` | NER / RE / EL / KG 写入 | NER/RE/EL 流水线 |
| **L1** ingestion | `packages/ingestion/` | PDF 解析 / 分块 / 去重 | `Parser` / `Chunker` / `Deduper` |
| 横切 | `packages/llm/` | LLM Gateway（无状态、library 无关） | `LLMClient` |
| 横切 | `packages/embedding/` | Embedder + Reranker（无状态） | `Embedder` / `Reranker` |
| 横切 | `packages/eventbus/` | 进程内事件总线（预留 Kafka 切换） | `EventBus` |
| 横切 | `packages/core/` | 领域模型 / config / errors（零外部依赖） | — |
| 终端包 | `packages/evaluation/` | 评测子系统（terminal package，没有任何包 import 它） | `EvalExecutor`, `MetricComputer`, `SandboxManager` |

### 5.3 依赖方向硬规矩

- 箭头方向只能单向 import
- 同层之间**不能**直接 import 实现，必须经由 `protocols.py`
- `core` 模块零依赖（除 `pydantic` + stdlib）
- `adapters/` 可 import 第三方库；`service.py` / `protocols.py` / `models.py` 禁止
- 校验：`tach check` 在 CI 中阻塞合并

### 5.4 每个 package 的标准结构

```
packages/<domain>/
├── __init__.py            # 只导出公开 API；__all__ 必须显式
├── protocols.py           # 对外 Protocol 接口（含 library_id 首参）
├── models.py              # 该领域 Pydantic 模型（引用 core.models）
├── errors.py              # 该领域异常
├── service.py             # 门面（Facade）—— 对外唯一入口
├── adapters/              # 具体实现（DB / 外部 SDK / 模型）
├── _internal/             # 包内私有，禁止跨包 import
└── tests/                 # 紧邻单元测试（可选）
```

**硬规矩**：

- 其他 package 只 `from packages.foo import X`，不准 `from packages.foo.adapters.bar import Y`
- `_internal/` 开头任何路径都视为私有；违规 CI 红

---

## 6. 数据层（六种存储后端各自承担什么）

### 6.1 角色分配

| 后端 | 在系统中的角色 | Library 隔离方式 | 命名规则 |
|------|--------------|----------------|---------|
| **PostgreSQL** | 元数据（Library / Document / Task / Eval）+ Outbox | `library_id` 列 + 复合索引 `(library_id, *)` | 不分 schema，RLS 可选 |
| **Qdrant** | 稠密向量检索（chunks 与 community summaries 分两 collection） | 一个 Library 一个 collection | `chunks_<library_id>`、`communities_<library_id>` |
| **Neo4j** | 知识图谱 / 实体-关系 / k-hop / PPR | 一个 Library 一个 composite database | `lib_<library_id>` |
| _（备选）_ Kuzu | 嵌入式 KG（替代 Neo4j 的轻量方案） | 一个 Library 一个 `.kuzu` 文件 | `data/kuzu/<library_id>.kuzu` |
| **OpenSearch / BM25** | 稀疏倒排索引 | 一个 Library 一个 index | `bm25_<library_id>` |
| _（备选）_ BM25S | 纯 Python 单机方案 | — | — |
| **MinIO** | 原始 PDF / 评测 artifact / community 摘要快照 | 一个 Library 一个 prefix | `s3://kb/<library_id>/...` |
| **Redis** | 缓存 / Arq 队列 / Token bucket 限流 | 一个 Library 一个 key prefix | `<library_id>:...` |

### 6.2 "删除一个 Library = 一条命令清干净"

- Qdrant：`delete_collection`
- Neo4j：`DROP DATABASE`
- OpenSearch：`DELETE /bm25_<id>`
- MinIO：`list+delete prefix`
- Postgres：`DELETE FROM ... WHERE library_id=`
- Redis：`SCAN+DEL` 按前缀

每个适配器实现 `init_library(library_id)` / `purge_library(library_id)`，由 `packages/core/library_admin.py` 顺序调用。

### 6.3 一致性

- 多存储写入用 **outbox 模式**：业务库写事务 → outbox 表 → 异步事件 → 各索引 upsert
- 每个 upsert 幂等，以 `(library_id, chunk_id)` 或 `(library_id, entity_id)` 为键

---

## 7. 检索栈：四索引 + RRF + Rerank + Agent

### 7.1 四个独立索引（per Library）

| 索引 | 用途 | 召回信号 |
|------|------|---------|
| **Vector** (Qdrant) | 稠密语义匹配 | BGE-M3 4096-dim 向量 |
| **BM25** (OpenSearch) | 精确术语 / 稀有词 | 传统倒排 |
| **Graph** (Neo4j) | k-hop 邻域 / 多跳 / 实体关联 | 三元组遍历 |
| **Community** (Qdrant 独立 collection) | 全局 / 综合性问题 | Leiden 社区摘要的向量召回 |

### 7.2 三段式 HybridRetrievalCoordinator

```
query ─┬─→ Vector top-K  ┐
       ├─→ BM25 top-K    ├─→ RRF 融合 ─→ Rerank ─→ top-K' ─→ LLM 生成
       ├─→ Graph k-hop   │              （BGE-reranker-v2）
       └─→ Community     ┘
```

**RRF**（Reciprocal Rank Fusion，Cormack 2009）：

```
score(c) = Σ_i 1 / (k + rank_i(c))     k = 60（默认）
```

**Reranker**：BGE-reranker-v2（library 无关），cross-encoder 重排 top-K → top-K'。

### 7.3 Local vs Global 路由（GraphRAG, ADR #6）

- **Local**：实体邻域 / chunk 级问题（"X 方法在 Y 场景的表现？"）
- **Global**：综合性问题（"领域主流方法有哪些？"）→ 读取 Leiden 社区摘要而非具体 chunk

路由器靠**问句词频 + 问句长度 + 实体命中率**做简单启发，10 道分类题准确率 ≥ 0.85（M3 Exit Criteria）。

### 7.4 Agent 检索策略（M4 落地）

`packages/retrieval/strategies/`：

- **DirectRAGPlanner**：M1 基线，无 loop，直接检索 → stuff → 答
- **ReActPlanner**：Thought / Action / Observation 循环
- **SelfRAGStyleCritic**：prompt-based 反思，模拟 Self-RAG 的 4 种 reflection token（不改 LLM 词表）
- **CRAGEvaluator**：轻量评估器（小 LLM 或 cross-encoder 分值阈值）+ 检索失败时兜底（query rewrite / web fallback）
- **ToGPlanner**：KG 上 beam search 多跳（深度 ≤ 3，beam ≤ 4）

**Query rewriter** (`packages/retrieval/rewriter.py`)：HyDE / Step-Back / decompose 三策略。

**Critic** (`packages/retrieval/critic.py`)：claim → evidence 对齐校验，必须验证 evidence chunk 与 query 同 library_id。

### 7.5 RetrievalBudget

```python
class RetrievalBudget(BaseModel):
    max_steps: int = 8
    max_llm_calls: int = 20
    max_tokens: int = 32_000
    timeout_s: float = 60.0
```

预算用尽 → `terminated_reason="budget_exceeded"`。可 per-Library 覆盖。

---

## 8. 知识图谱构建与 Community

### 8.1 KG 抽取流水线（L2 structuring）

```
chunk → NER (GLiNER 零样本) → RE (LLM REBEL 风格)
              ↓                       ↓
        实体集合           三元组 + provenance chunk_id
              ↓
       EntityLinker (字符串 + embedding 双阶段)
              ↓
       KGWriter (Neo4j MERGE，幂等)
```

### 8.2 实体类型（六类，UI/UX 中有专属配色）

| 类型 | 色 | 中文 |
|---|---|---|
| Concept | `#4F46E4`（cobalt） | 概念 |
| Method | `#10B881`（emerald） | 方法 |
| Dataset | `#F59E0A`（amber） | 数据集 |
| Metric | `#06B6D3`（cyan） | 指标 |
| Author | `#A854F7`（violet） | 作者 |
| Venue | `#EB4799`（pink） | 会议/期刊 |

### 8.3 Schema 管理

- YAML 配置 + 运行时校验
- **Schema 可 per-Library 覆盖**：`docs/ontology/<library_id>/v1.yaml`
- 非法关系直接拒绝写入
- 反幻觉硬约束：三元组的 head/tail **必须**在 evidence chunk 的文本中出现

### 8.4 Community 检测与摘要（M3，GraphRAG-Global）

- **CommunityDetector**：Leiden 算法（`leidenalg`），层级 C0 / C1 / C2 / C3
- **CommunitySummarizer**：LLM 对每个社区生成 150–300 字摘要，含 3–5 个代表实体
- **CommunityIndex**：摘要文本入向量库独立 collection `communities_<library_id>` + Postgres 元数据
- **增量重建**：仅重算受影响的社区，不阻塞在线查询
- **Leiden vs Louvain**（ADR #4）：选 Leiden 因为 connectivity 保证 + 更稳定

### 8.5 KG 数据模型

```python
class Entity(BaseModel):
    library_id: str
    entity_id: str        # canonical ID, library 内唯一
    name: str
    aliases: list[str]
    type: str             # concept / method / dataset / metric / author / venue
    description: str | None

class Triple(BaseModel):
    library_id: str
    head: str             # 必须与 head Entity 同 library_id
    relation: str
    tail: str
    evidence: list[str]   # chunk_ids（必须同 library_id）
    confidence: float
    source_model: str
```

全部 `frozen=True, extra="forbid"`。

---

## 9. Agent 编排与四种 Planner

### 9.1 编排原则（L5 orchestration）

- 任务模板限定单 Library（`TaskRunner` 首参 `library_id`）
- 长任务（综述 5–15 min）封装为 Arq job，支持后台运行、断点续跑
- 进度通过 SSE 推送结构化阶段事件：`stage_started` / `stage_progress` / `stage_completed` / `task_completed`

### 9.2 任务通用框架

```python
class TaskRunner:
    async def run(
        self,
        library_id: str,
        task_input: TaskInput,
        *,
        dry_run: bool = False,
        cost_estimate: bool = False,
        stream_progress: bool = True,
    ) -> TaskResult: ...
```

### 9.3 反思与校正循环

```
1. Plan       ← LLM 拆解问题为子目标
2. Retrieve   ← 调 L4
3. Critic     ← claim-evidence 对齐校验
4. Rewrite?   ← Query rewriter（HyDE / Step-Back / decompose）
5. Synthesize ← LLM 生成 + 引用
6. Verify     ← 二次 critic
```

如果任一环节失败：
- 检索失败 → CRAG fallback（rewrite / 换策略 / 给出空答案而非幻觉）
- 引用失败 → Self-RAG critic 重新生成
- 预算耗尽 → 返回部分答案 + `terminated_reason`

### 9.4 RetrievalTrace（全程落 Langfuse）

```python
class RetrievalStep(BaseModel):
    step_idx: int
    thought: str
    action: str
    action_input: dict[str, object]
    observation: str
    cost: StepCost

class RetrievalTrace(BaseModel):
    library_id: str                         # 全程绑定
    steps: list[RetrievalStep]
    final_evidence: list[RetrievedEvidence] # 每条 library_id 必须一致
    budget_used: BudgetUsage
    terminated_reason: Literal["answer_ready", "budget_exceeded", "error"]
```

---

## 10. 五大科研任务（UC1–UC5）

| UC | 名称 | 输入 | 输出 | 实现层 |
|----|------|------|------|------|
| **UC0** | Library 管理 | slug + 元数据 | Library CRUD | apps + `library_admin` |
| **UC1** | **精准问答** | 自然语言 + library_id | 带引用答案 + 证据片段 | `QATask` |
| **UC2** | **实体透视** | 实体名 + library_id | KG 子图 + 邻接三元组 | `GET /entities/{id}/neighborhood` |
| **UC3** | **主题综述** | 主题 + 年份范围 + 字数 + 引用风格 | 结构化综述草稿（Markdown + 引用） | `ReviewGenerationTask` |
| **UC4** | **跨文献推理** | 多跳问题 | KG 路径 + 证据时间线 + 结论 | `CrossPaperReasoningTask` |
| **UC5** | **假设生成** | 实体对（A, B）| 候选假设 + 三维评分 + KG 路径 | `HypothesisTask` |

### 10.1 综述生成（UC3）细节

- 用户配置：年份范围、目标字数（1500 / 3000 / 5000）、引用风格（编号 / 作者-年份）、可选手动子主题
- 流程：主题 → 全局召回 → LLM 切分子主题 → 每子主题 local search → 拼接 → 写作 → 引用核对
- 输出：Markdown 草稿 + 完整 `citations[]`
- 验收：3000 字 ≤ 10 min，引用正确率 ≥ 0.85

### 10.2 跨文献推理（UC4）细节

- 问题分解 → 并行检索 → ToG 在 KG 上跑 meta-path → 聚合 + 证据回填
- 输出：结构化 path（`list[(entity, relation, entity)]`），前端 KG 浏览器可视化
- 验收：20 题 3 跳问题答案正确率 ≥ 0.60

### 10.3 假设生成（UC5）三维评分

| 维度 | 计算 | 含义 |
|------|------|------|
| **novelty** ∈ [0,1] | 与已知文献结论的重叠度（embedding 距离 + 引用计数反向） | 新颖性 |
| **confidence** ∈ [0,1] | KG 路径数 × 路径置信度的几何均值 | 置信度 |
| **verifiability** ∈ [0,1] | 路径是否含 Method / Dataset 节点的启发式 | 可验证性 |

排序按 `novelty × confidence` 降序。每条假设携带：陈述 + 解释 + KG 路径 + 反驳证据。

---

## 11. 评测体系：8 指标 + 三种执行模式

### 11.1 8 指标矩阵（5 deterministic + 3 LLM-Judge）

| Metric | 类别 | 实现 | 依赖 |
|--------|------|------|------|
| `RecallAtK` | deterministic | retrieved doc_ids ∩ expected | 无 LLM |
| `MustNotContain` | deterministic | 字符串/正则匹配 | 无 LLM |
| `Latency` | deterministic | `result.duration_ms` | 无 LLM |
| `Cost` | deterministic | 累加 token usage | 无 LLM |
| `CitationF1` | mixed | 抽 claim → 验 cite chunk 含支持文本 | 轻量 LLM-Judge |
| `Faithfulness` | LLM-Judge | Ragas 实现 | LLM-Judge |
| `AnswerRelevancy` | LLM-Judge | Ragas | LLM-Judge |
| `KeyPointCoverage` | LLM-Judge | 判 expected_key_points 命中数 | LLM-Judge |

**LLM-Judge 防自欺**（EVAL_ARCHITECTURE §4.6）：Judge 与生成走不同模型族（如生成用 Claude → Judge 用 Qwen2.5-72B；生成用 GPT → Judge 用 Claude Sonnet）。每月抽 30 sample 人工校准，一致率 < 0.85 触发 Judge prompt 重调。

### 11.2 三种执行模式（EVAL_ARCHITECTURE §3）

| Mode | 何时用 | 机制 | 代价 |
|------|-------|------|------|
| **A. Live** | 发布前 / 月度审计 / 人工抽查 | 真实 Library 跑全套 | 贵 + 慢 |
| **B. Sandbox**（默认） | 每天 nightly / PR 阻塞 / 回归测试 | 从固定黄金语料重建临时 `_eval_<suite>_<runid>` Library，跑完即销毁 | 5–10 min |
| **C. Replay** | 改 prompt / LLM 路由，不改检索 | 从 Langfuse 拉历史 `(query, retrieved_chunks, llm_input)`，复用检索结果，只重跑生成 + 评分 | 极低 |

### 11.3 评测集组织（per Library）

```
data/libraries/<library_id>/evals/
├── qa.smoke.v1.yaml         # 每库至少 10 题
├── qa.multihop.v1.yaml      # 每库至少 30 题
└── review.v1.yaml           # 每库至少 5 主题
```

- 自动生成：`rkb eval generate --library <id>` 让 LLM 从 chunk 生成 QA 对（draft），人工审核后标记 `human_validated: true`
- 主 Library 作为 PR 阻塞门槛；其他 Library nightly 跑
- 评测样本 schema 含 `library_id`

### 11.4 EvalSample / EvalRun 模型

```python
class EvalSample(BaseModel):
    sample_id: str
    library_id: str
    suite: str                            # "qa.smoke" / "review.v1"
    suite_version: str
    question: str | None
    inputs: dict[str, object]
    expected_evidence_doc_ids: list[str]
    expected_key_points: list[str]
    must_not_contain: list[str] = []
    difficulty: Literal["easy", "medium", "hard"]
    type: Literal["single-hop", "multi-hop", "global", "definition"]
    acceptable_score_floor: float = 0.7
    human_validated: bool = False

class EvalRun(BaseModel):
    run_id: UUID
    suite: str
    library_id: str                       # 实际跑的 lib（可能 _eval_*）
    source_library: str                   # 评测集所属
    system_version: str                   # git SHA
    mode: Literal["live", "sandbox", "replay"]
    ...
```

### 11.5 评测系统的 8 条设计原则

| # | 原则 | 含义 |
|---|------|------|
| P1 | 走正门 | Eval 作为正常客户端调用 L5；不开后门 |
| P2 | 数据隔离 | `library_id = "_eval_*"` 物理隔离 |
| P3 | 模型隔离 | Judge 与生成模型不同 |
| P4 | 成本可见 | 每 sample 的 token / $ 显式入库 |
| P5 | 可追溯 | 每 sample 输出有 trace_id + artifact |
| P6 | 可重放 | Replay mode 零边际成本回归 prompt |
| P7 | 不污染依赖 | `evaluation` 是 terminal package |
| P8 | Library 维度感知 | 评测集 per-Library 组织；指标按 Library 切分 |

### 11.6 输出三路

1. Markdown table → PR comment
2. Prometheus push → Grafana dashboard
3. Baseline diff → 阻塞 / 告警

---

## 12. M0–M8 里程碑全景

### 12.1 总览

| # | 里程碑 | 代号 | 周期 | 状态 | 主要能力 |
|---|-------|-----|------|------|---------|
| **M0** | 工程地基 | Foundation | 2 周 | ✅ | 仓库骨架 / CI / 数据层 compose / 核心模型 / Library 字段贯穿 |
| **M1** | Minimum Viable RAG | MVP-RAG | 3 周 | ✅ | PDF 摄取 / 向量索引 / 最简 QA 带引用 |
| **M2** | KG + 混合检索 | GraphFusion | 3 周 | ✅ | NER/RE/EL / 图索引 / BM25 / Rerank |
| **M3** | Community + 全局检索 | GraphRAG-Global | 2 周 | ✅ | Leiden 社区 + 摘要 + Global Search + Local/Global 路由 |
| **M4** | Agentic Retrieval | AgentLoop | 3 周 | ✅ | Self-RAG / CRAG / ToG / planner / critic / rewriter |
| **M5** | 科研任务模板 | ScientificTasks | 3 周 | ✅ | Review / Reason / Hypothesis 三类任务 |
| **M6** | 评测与可观测 | QualityLoop | 2 周 | ✅ | 8 指标 / Ragas / Langfuse / OTel / CI gate |
| **M7** | 硬化与 UX | Hardening | 3 周 | ✅ | Vue 3 web UI / OpenAPI 契约 / ingest 幂等 / library 备份 / 安全审查 |
| **M8** | 面向未来 | FutureProof | 持续 | ✅ | 多轮会话 / 研究记忆 / query 改写 / 性能基线 / v2 预研 |

**累计**：约 21 周（5 个月）达到 v1.0；M8 持续演进。

### 12.2 依赖关系

```
M0 → M1 → M2 → M3 ─┐
              └─ M4 ┴─ M5 ─ M6 ─ M7 ─ M8
```

M4 可在 M3 完成后并行启动。

### 12.3 Release 节奏

| 阶段 | 版本 | 对象 | 标准 |
|------|------|------|------|
| 内部 α | v0.7 (M6) | 开发者自用 | 功能完整 |
| 外部 α | v0.9 (M7) | 3–5 位真用户 | VAR ≥ 0.60 |
| β | v1.0-rc | 10–30 位用户 | VAR ≥ 0.70 |
| **GA** | v1.0 | 公开 | VAR ≥ 0.75；无 P0/P1 |

### 12.4 异步任务现状

PRD §M5 设计了 Arq worker；当前所有任务（ingest / QA / review / reason）在 CLI/API 进程内**同步执行**。`apps/worker/main.py` 里的 `noop` 函数只是为了让 worker 进程能启动通过 arq 的 `functions 非空` 校验。未来异步化时在 `WorkerSettings.functions` 注册真实任务即可。

---

## 13. 23 个 ADR 一句话索引

> 完整 ADR 在 `docs/adr/`。下表给一句话定位。

| # | 文件 | 一句话 |
|---|------|--------|
| 0001 | modular-monolith | 选模块化单体而非微服务，演进可控 |
| 0002 | toolchain-selection | Python 3.12 / uv / ruff / pyright strict / FastAPI / Arq |
| 0003 | library-as-data-partition | **Library 是数据分区**，不开 package、不进分层（核心架构决策） |
| 0004 | community-detection-louvain-vs-leiden | 选 Leiden 因为 connectivity 保证 + 稳定性 |
| 0005 | community-summary-prompt-design | Community 摘要 prompt 设计（150–300 字 + 3–5 代表实体） |
| 0006 | local-vs-global-routing | Local vs Global 路由策略（启发：词频 + 长度 + 实体命中） |
| 0007 | m7-error-envelope-and-sse | 统一 ApiError 信封 + SSE 事件流契约 |
| 0008 | context-management | 多轮会话上下文压缩与改写策略 |
| 0009 | async-task-queue | Arq 选型 + 长任务断点续跑 |
| 0010 | sse-task-progress-events | 任务进度结构化事件（stage_started / stage_progress / ...） |
| 0011 | notification-center | 顶栏 Notify 中心 + 通知数据模型 |
| 0012 | per-library-config-overrides | per-Library 配置覆盖体系（LLM 路由 / Embedder / 预算） |
| 0013 | library-status-machine | Library 三态 Healthy / Indexing / Stale community |
| 0014 | activity-log-l5-aggregation | 跨 Library 活动流是 L5 编排聚合，不破规矩 |
| 0015 | daily-cost-cap | 每 Library 每日成本上限 + 超限阻断 |
| 0016 | var-computation | VAR 计算口径（用户标记 + 自动评分混合） |
| 0017 | self-rag-and-strategy-routing | Self-RAG 风格 critic 用 prompt 模拟，不改 LLM 词表 |
| 0018 | reranker-selection | BGE-reranker-v2 选型 + 阈值 |
| 0019 | zip-folder-upload-pipeline | ZIP / 文件夹批量上传的解析管道 |
| 0020 | hypothesis-scoring | 假设三维评分（novelty × confidence × verifiability） |
| 0021 | eval-alerts | VAR 周环比下跌 > 5pp 告警策略 |
| 0022 | library-purge-atomicity | Library purge 的原子性（软删 30 天 + 硬删 drill） |
| 0023 | command-palette-search | ⌘K 全局命令面板搜索体系 |

---

## 14. 前端：Vue 3 + Cobalt Lab 设计系统

### 14.1 技术栈

- **Vue 3.4+** Composition API + `<script setup lang="ts">`
- **Pinia**（状态管理）
- **Vue Router 4**
- **Naive UI**（原子组件库，但业务层不直接 import，全部经 `components/base/*` 薄包装）
- **UnoCSS**（atomic CSS，token-bound class）
- **ECharts**（KPI 趋势图）
- **Cytoscape.js**（KG 力导向可视化）
- **vue-i18n**（zh-CN + en-US）
- **openapi-typescript**（DTO 由 `/openapi.json` 自动生成；前端不手写类型）

### 14.2 信息架构（UI_UX §2）

```
/onboarding                        # 无 Library 时的引导
/libraries                         # Library 仪表盘（全局首页）
/lib/:libraryId                    # ★ 所有 Library-scoped 页面挂在此
    /                              # Library 概览（Stats）
    /chat[/:sessionId]             # 主 Chat / QA（默认入口）
    /docs[/:docId]                 # 文献库
    /kg                            # 知识图谱浏览器
    /review[/:taskId]              # 综述生成
    /reason[/:taskId]              # 跨文献推理
    /hypothesize[/:taskId]         # 假设生成
    /eval                          # 评测仪表板
    /settings                      # Library 设置
/settings                          # 全局设置
```

**URL 强约束**：所有 Library-scoped 页面 URL 必含 `:libraryId`；切库 = 路由跳转 + 自动清空 store。

### 14.3 8 个核心屏幕（FRONTEND_DESIGN_SPEC + UI_UX §6）

| 屏 | 路径 | 角色 |
|---|------|------|
| S1 | `/onboarding` | 首次引导，3 步说明卡 + Create your first Library CTA |
| S2 | `/libraries` | 跨 Library 仪表盘（卡片 + KPI + Recent Activity） |
| **S3** ★ | `/lib/:id/chat` | **旗舰屏**：三栏（Nav + Conversation + Evidence）+ SSE 流式 + CitationChip + Reasoning Trace |
| S4 | `/lib/:id/kg` | KG Browser：Filter + Cytoscape 画布 + Entity Detail Drawer |
| S5 | `/lib/:id/review` | 综述生成（配置 → 进行中 → 完成三态） |
| S6 | `/lib/:id/docs` | 文档列表 + DropZone + 5 态摄取进度 |
| S7 | `/lib/:id/reason` + `/hypothesize` | 跨文献推理（path 可视化）+ 假设卡（三轴评分） |
| S8 | `/lib/:id/eval` + `/settings` | 评测仪表 + KPI 卡 + 趋势图 + Library 设置 |

### 14.4 4 个 Modal / Overlay

| Modal | 用途 |
|---|---|
| M1 LibraryCreateModal | 建库向导（slug + 名称 + 描述 + 主语言） |
| M2 DeleteConfirmModal | 删库二次确认（输入完整 slug 才能确认） |
| M3 CommandPaletteOverlay | ⌘K 全局命令面板（实体 / 文档 / 任务搜索 + 快捷动作） |
| M4 DocumentDetailDrawer | 文档详情（PDF preview + 章节大纲 + chunk 列表） |

### 14.5 Cobalt Lab 设计系统（FRONTEND_RULES §1）

- **色板**：
  - Neutrals（暖灰）：`bg-canvas #FAFAF9` / `bg-surface #FFFFFF` / `bg-subtle #F4F4F1` / `text-primary #1A1A1A` …
  - Brand（钴蓝紫）：`brand-500 #4F46E4`（主交互色）/ `brand-600 #3B30D9`（hover）
  - Semantic：success `#10B881` / warning `#F59E0A` / danger `#EE4444` / info `#06B6D3`
  - **CitationChip 用 info-cyan**，与 brand 区隔（视觉上"这是引用"而非"按钮"）
  - 6 类 KG 实体专属色
- **字体**：Inter UI + JetBrains Mono（chunk_id / DOI / 数值）
- **间距**：4px base（4/8/12/16/20/24/32/40/48/64）
- **圆角**：chip 6 / button 10 / card 14 / modal 20 / pill 999
- **阴影**：sm / md / lg + focus 环 `0 0 0 3px rgba(79,70,229,.20)`
- **动效**：hover 120ms / modal 200ms / 流式 caret 22ms/token

### 14.6 5 个领域级自定义组件（UI_UX §5.2）

1. **LibrarySwitcher** — 顶栏下拉，含搜索 / 最近 / 固定置顶 / + New Library
2. **CitationChip** — `[12]` info-cyan pill，hover 弹预览（标题+作者+段落首句），click → 滚动到 EvidencePanel
3. **EvidencePanel** — 右侧 440px / 360px 抽屉，每条证据：标题 + 元数据 + 命中文本（高亮 query 词）+ score + source 图标
4. **KGCanvas** — Cytoscape 包裹，顶部工具栏（深度 / 类型 filter / fit / 导出 PNG）
5. **TaskProgress** — 长任务面板：阶段步骤树 + 实时日志 SSE 流 + 取消/后台

### 14.7 前端硬规矩（FRONTEND_RULES）

- 业务层禁止 import Naive UI 原子；都经 `components/base/*` 薄包装
- 所有色值用 CSS variables / UnoCSS theme token；禁止 hex 字面量
- TypeScript strict；禁 `any`，外部输入用 `unknown`
- 双语：每个可见字符串在 `i18n/locales/{zh-CN,en-US}.ts` 双语补齐；CI 校验 key 集合一致（`pnpm i18n:check`）
- 测试：base 组件 ≥ 80% 覆盖；Playwright 5 条 E2E（建库→上传→提问→综述→评测面板）

### 14.8 设计稿来源与 UI 提示词

- 设计稿 Figma file `A1CKNzyz03sw6iXHvOo2IM`（14 frame）
- `docs/FRONTEND_DESIGN_SPEC.md` 是 Figma REST API 提取的实测 token + 14 frame 层级
- `docs/UI_PROMPTS.md`（9,546 行）是从 Figma 提取的提示词手册：91 个独立可复制 prompt，每个内嵌完整 Cobalt Lab preamble，可粘贴到 v0 / UX Pilot / Midjourney 等 UI 生成器
- `scripts/generate_ui_images.py` 是配套的批量生图脚本（stdlib + 并发 6 + 4 次指数退避重试 + 断点续跑 + 自动生成 `UI_GALLERY.md`）

---

## 15. HTTP API 全景

**Base URL**：`http://localhost:8000`（默认）

### 15.1 健康 / 自描述

| Method | Path | 说明 |
|--------|------|------|
| GET | `/healthz` | Liveness — 永远 200 |
| GET | `/readyz` | Readiness |
| GET | `/metrics` | Prometheus 指标 |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | 原始 OpenAPI 3 schema |

### 15.2 Library CRUD

| Method | Path | 说明 |
|--------|------|------|
| POST | `/v1/libraries` | 创建 Library（201 / 409 `LIBRARY_ALREADY_EXISTS`） |
| GET | `/v1/libraries` | 列表 |
| GET | `/v1/libraries/{library_id}` | 详情 + 统计 |
| DELETE | `/v1/libraries/{library_id}` | 删除（hard-remove Postgres + Qdrant + Neo4j + MinIO） |
| DELETE | `/v1/libraries/{library_id}?purge=1` | 硬删（同步物理清除） |

### 15.3 文档摄取

| Method | Path | 说明 |
|--------|------|------|
| POST | `/v1/libraries/{library_id}/ingest?force=false` | multipart PDF 上传；SHA-256 幂等 |

### 15.4 问答（QA）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/v1/libraries/{library_id}/qa` | 一次性返回 `QAResponse`（citations 是唯一权威 chunks） |
| GET | `/v1/libraries/{library_id}/qa/stream?question=...` | **SSE 流式**：`event: meta` / `token` / `citations` / `done` / `error` |

### 15.5 知识图谱

| Method | Path | 说明 |
|--------|------|------|
| GET | `/v1/libraries/{library_id}/entities/{entity_id}/neighborhood?depth=1..3` | 邻域三元组 |
| GET | `/v1/libraries/{library_id}/schema` | 实体类型 + 关系类型 + 颜色（12 色 colorblind-safe palette） |
| GET | `/v1/libraries/{library_id}/stats` | docs / chunks / entities / triples / communities / summary_freshness_iso |

### 15.6 生成任务

| Method | Path | 说明 |
|--------|------|------|
| POST | `/v1/libraries/{library_id}/review` | 综述生成（topic → ReviewResponse with sections + citations） |
| POST | `/v1/libraries/{library_id}/hypothesis` | 假设生成（head_entity_id + tail_entity_id → hypotheses with confidence + counter_evidence） |

### 15.7 错误码

```
VALIDATION_ERROR        # 400, 422
AUTH_ERROR              # 401, 403
NOT_FOUND               # 404 generic
LIBRARY_NOT_FOUND       # 404 specific
LIBRARY_ALREADY_EXISTS  # 409
CONFLICT                # 409 generic
RATE_LIMITED            # 429 + Retry-After header
UPSTREAM_ERROR          # transient external failure
INTERNAL_ERROR          # 500
```

每个响应带 `X-Request-Id`；统一信封 `ApiResponse[T] { success, data, error, meta }`。

---

## 16. CLI（rkb）命令全景

`uv run rkb <command>` 或 `make cli -- <command>`。全局 `--library <id>` 或环境变量 `RKB_LIBRARY=<id>`；个人便利在 `~/.rkb/config.toml`。

| 命令 | 说明 |
|------|------|
| `rkb version` | 版本 |
| `rkb library create <slug> [--name ...]` | 创建 Library |
| `rkb library list` | 列出 |
| `rkb library delete <slug> [--purge]` | 删除（默认软删 30 天） |
| `rkb library export <slug> --out <path>` | 导出（含 Qdrant collection / Neo4j DB / BM25 index / MinIO prefix） |
| `rkb library import <path> --as <new-slug>` | 跨机器迁移 |
| `rkb library neighborhood --library <id> --entity <e> --depth 2` | 邻域查询 |
| `rkb ingest --library <id> <path> [--force]` | 摄取单文件 / 目录 / ZIP |
| `rkb qa --library <id> --question "..."` | 问答 |
| `rkb review --library <id> --topic "..."` | 综述生成 |
| `rkb eval generate --library <id>` | LLM 从 chunk 自动生成 QA 对 draft |
| `rkb eval run --library <id> --suite qa.smoke` | 跑评测 |

---

## 17. 数据组织：`data/libraries/`

```
data/
├── README.md
└── libraries/
    └── <library_id>/
        ├── corpus/             # 用户语料（PDF / ZIP / 文件夹）→ 不入 git
        └── evals/              # 评测集（YAML）→ 入 git
            ├── qa.smoke.v1.yaml
            ├── qa.multihop.v1.yaml
            └── review.v1.yaml
```

- `corpus/` 大文件**不入 git**（`.gitignore` 排除）
- `evals/` YAML **入 git**，作为评测金牌集
- 评测集支持自动生成（`rkb eval generate`），人工审核后标 `human_validated: true`

---

## 18. 配置 / 安全 / i18n / 可观测性 / 成本控制

### 18.1 配置（CODING_STANDARDS §10）

- 单一来源 `packages/core/config.py`，pydantic-settings
- 优先级：`env var > .env > 默认值`
- 业务代码**禁止**直接读 `os.environ`
- per-Library 配置覆盖（M7 落地）：LLM 路由 / Embedder / 检索预算 / 每日成本上限

### 18.2 安全（PRD §16.4）

- 密钥不入库；pre-commit `gitleaks`
- `Authorization: Bearer <token>` 可选（`API_KEY` 环境变量）
- 摄取数据版权由用户自担；系统仅支持用户合法持有的文献
- M7 完成一次 `security-review` 审查；输出 `docs/SECURITY_REVIEW_M7.md`
- 本地部署优先，数据不出本机/机房
- 输入边界校验（Pydantic）；日志不暴露密钥 / 内部路径

### 18.3 i18n

- zh-CN（默认）+ en-US；vue-i18n
- 持久化在 localStorage
- CI 校验 key 集合一致：`pnpm i18n:check`
- 所有 placeholder / error 走 i18n
- 翻译走 PR 到 `apps/web/src/i18n/locales/`

### 18.4 可观测性（CODING_STANDARDS §11）

- **structlog** JSON 结构化日志（禁 `print` / `f"..."` 拼字符串）
- **OpenTelemetry** trace 覆盖 L1–L5 关键 span（含 `library_id` 标签）
- **Langfuse** 自托管，LLM 全量 trace（按 Library 分项目或加 tag）
- **Grafana**：VAR 趋势 / Citation F1 / P95 / cost；Library 维度过滤
- **Prometheus 指标**：
  - HTTP：`http_requests_total{route, status}` / `http_duration_seconds`
  - 检索：`retrieval_hits_total{source}` / `retrieval_duration_seconds`
  - LLM：`llm_tokens_total{model, type}` / `llm_cost_usd_total`
  - 队列：`ingest_queue_depth` / `ingest_lag_seconds`
- 采样率：开发 100% / 生产 10%
- 告警：VAR 周环比下跌 > 5pp 告警（按 Library 分别）

### 18.5 成本控制

- Embedding 缓存（SQLite）—— 同文本不重复 embed
- Ingest 幂等（SHA-256 dedup）—— 同 PDF 不重复处理
- KG 抽取受 schema gate；dev 默认关闭 raw extraction
- 检索 planner 选最便宜的有效模式（direct → hybrid → routed → ReAct）
- per-Library 每日成本上限：超限阻断新任务并提示用户
- 所有 LLM / embedding / cost 指标暴露在 `/metrics`
- 可选 `rate_limit_enabled` per-route 限流

---

## 19. 部署：Docker Compose + Makefile

### 19.1 前置

- Python 3.12+
- `uv`（包管理器）
- Docker + Docker Compose

### 19.2 5 步本地启动（README）

```bash
# 1. Clone and install
git clone <repo-url> && cd rag-kg-copilot
make install                # uv sync

# 2. Start data layer
make up                     # docker compose up -d (6 服务)

# 3. Verify health
make api                    # FastAPI on :8000
curl http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}

# 4. Quality gates
make lint                   # ruff check + format
make typecheck              # pyright --strict
make test                   # pytest
make test-cov               # 80% coverage gate

# 5. Explore CLI
make cli -- version
make cli -- library list
```

### 19.3 Makefile 目标

| Target | 说明 |
|--------|------|
| `make install` | `uv sync` |
| `make up` / `make down` | 启停数据层容器 |
| `make api` | FastAPI dev server |
| `make worker` | Arq worker（M7 当前 noop） |
| `make cli` | CLI |
| `make lint` | ruff lint + format check |
| `make typecheck` | pyright strict |
| `make test` | pytest |
| `make test-cov` | tests with 80% coverage gate |
| `make eval` | 跑评测集（输出 markdown） |
| `make arch` | tach check（依赖方向） |

### 19.4 CI 红线（CODING_STANDARDS §20）

| 阶段 | 命令 | 说明 |
|------|------|------|
| 安装 | `uv sync --frozen` | 锁定依赖 |
| 格式 | `ruff format --check .` | 未格式化拒 |
| Lint | `ruff check .` | 违规拒 |
| 架构 | `tach check` | 依赖方向 |
| 类型 | `pyright` | strict |
| 单测 | `pytest tests/unit -x --cov=packages --cov-fail-under=80` | 80% gate |
| 集成 | `pytest tests/integration` | PR 必过 |
| 安全 | `gitleaks detect` | 扫泄密 |
| 依赖 | `uv pip check` + `pip-audit` | 漏洞 |

**Nightly**：E2E + Ragas / LitQA 评测 + `uv sync --upgrade` 演练

### 19.5 备份与恢复

- **per-Library 粒度**：`rkb library export <id> --out <path>` 导出 Postgres 行 / Qdrant collection / Neo4j DB / MinIO prefix（含索引数据）
- **跨机器迁移**：`rkb library import <path> --as <new-id>`
- **全局 snapshot**：脚本备份所有 Library

---

## 20. 非目标 / 已知边界 / v1.1+ 计划

### 20.1 v1 非目标（PRD §4.2）

| 项 | 理由 |
|---|------|
| 多租户 / 鉴权 / 计费 / SaaS | 多 Library ≠ 多租户 |
| **跨 Library 联合查询** | 用客户端多次调用解决；v2+ 再考虑底层支持 |
| 移动端 / iOS / Android | 非主要使用场景 |
| 自动跑湿实验 | 超出定位 |
| 完整 AI Scientist-v2 等级的自主科研 | v2+ 目标 |
| 商业闭源模型独占依赖 | 必须支持全本地方案 |
| 实时（秒级）同步外部数据源 | 每日批同步即可 |

### 20.2 v1.1+ 显式延后

- 假设生成的 KG embedding 路径挖掘（TransE / RotatE）
- Hypothesis tournament（AI co-scientist 风格 Generate-Debate-Evolve）
- 多用户协作 / 评论 / 标注
- **跨 Library 联合数据查询**（差异分析 / 共性发现，覆盖 L1-L4 数据层；v1 仅允许 L5 编排层只读元视图）
- 插件化外部工具（Wolfram / 代码执行）
- 移动端

### 20.3 M8 候选池（v2 预研）

- 性能基线（每周跑一次，性能退步自动告警）
- 抽服务预演（最可能外抽 `llm` 或 `embedding`）
- 完整 AI co-scientist 式多 Agent
- KG embedding 路径挖掘（TransE / RotatE）做高级假设
- Deep Research 风格自动综述
- Zotero / Obsidian / VS Code 插件

### 20.4 风险登记册（PRD §17）

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R01 | LLM 成本失控 | 中 | 高 | Gateway per-request cap + 小模型优先路由 |
| R02 | PDF 解析质量拖累下游 | 中 | 高 | 多解析器并存（Nougat + MinerU）+ 人工抽检 |
| R03 | KG 抽取幻觉 | 高 | 高 | Schema 约束 + provenance 强校验 |
| R04 | 评测集过小指标噪音 | 中 | 中 | 每月扩充；不同任务分桶 |
| R05 | 个人项目倦怠 | 中 | 高 | 里程碑切小；每周可见进展；Demo 驱动 |
| R06 | 依赖库重大升级破坏 | 低 | 中 | 锁依赖 + 月度升级演练 |
| R07 | 硬件瓶颈（单机 GPU） | 中 | 中 | API 模型 fallback；M8 抽服务 |
| R08 | Schema 提前冻结不合理 | 中 | 中 | Bottom-up 诱导 + evolution 窗口 |
| R09 | Neo4j/Qdrant 数据丢失 | 低 | 高 | M7 备份脚本 + 周期恢复演练 |
| R10 | 用户期望错配（当 ChatGPT） | 中 | 中 | User Guide 明确定位；UI 强调可追溯 |
| R11 | **Library 数据混淆**（A 的 chunk 出现在 B 的回答） | 低 | 高 | Pydantic validator 拒跨 Library；适配器物理隔离；每里程碑回归测 |
| R12 | Library 概念被误用为"模块/服务" | 中 | 中 | ADR #3 反复声明；Code Review checklist 硬条目 |
| R13 | Library 多到管理混乱 | 中 | 低 | UI Stats + 软删保留 30 天 |

---

## 21. 入门路径与"重新进入项目"的快速通道

### 21.1 给一个完全不懂这个项目的人（30 分钟）

按顺序读：

1. **`README.md`**（10 min）— 大致定位 + 5 步启动 + 路线图
2. **本文件 §1–§4**（5 min）— 愿景 + 主要思想 + Library 概念
3. **`docs/USER_GUIDE.md`**（10 min）— 用户视角的 15 分钟首次使用
4. **`docs/UI_UX.md` §0–§3**（5 min）— 设计原则 + Cobalt Lab 色板

### 21.2 给一个回归开发者（"我忘了怎么做的"，1 小时）

1. 本文件全文（30 min）
2. `docs/PRD.md` 目录扫一遍（10 min）—— 知道每个里程碑做了什么
3. `docs/CODING_STANDARDS.md` §2 / §3 / §6.5 / §12.5（10 min）—— 工程规矩 + Library 维度纪律
4. `docs/adr/0001-modular-monolith.md` + `0003-library-as-data-partition.md`（10 min）—— 两条架构红线

### 21.3 给一个改后端代码的（2 小时上手）

1. 上面 §21.2 全套
2. 读目标 package 的 `protocols.py` + `service.py`
3. `docs/API_REFERENCE.md`（如果改 API）
4. `docs/EVAL_ARCHITECTURE.md` §1–§5（如果改检索/生成，必须懂评测系统的"走正门"原则）
5. 运行 `make typecheck && make test`

### 21.4 给一个改前端的（1.5 小时上手）

1. 上面 §21.1 全套
2. `docs/FRONTEND_RULES.md` 全文（30 min）—— 硬规矩
3. `docs/FRONTEND_DESIGN_SPEC.md` §1（Design Tokens 部分）+ 自己要改的 frame（20 min）
4. `docs/UI_UX.md` §4–§6（信息架构 + 8 屏规格）
5. `docs/UI_PROMPTS.md` 对应组件 prompt（如果要补设计稿）

### 21.5 给一个看不到屏幕但想感受设计的

1. `docs/UI_PROMPTS.md` 顶部目录（5 min）
2. 运行 `python scripts/generate_ui_images.py --limit 5` → 看 `docs/UI_GALLERY.md` 前 5 张缩略图

### 21.6 一句话最高级摘要

> **本项目 = "用 Library 物理分区把研究方向各自独立；用稠密知识图谱 + 多索引检索给 LLM 加上可追溯记忆；用 Agent 编排把 4 类科研任务（问答 / 综述 / 多跳推理 / 假设生成）做成闭环；用持续评测（VAR ≥ 75% / Citation F1 ≥ 0.85）卡住质量退化"。**

---

**END — 本文档是项目的"地图 + 记忆点"。具体技术细节请回到对应原文档。**
