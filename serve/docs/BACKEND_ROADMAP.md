# Backend Roadmap — RAG-KG Copilot · M7 收口

**文档状态**：v0.1 / Draft
**对齐版本**：PRD v0.2（2026-05-05 对齐过原型后）+ `docs/UI_UX.md` v0.1
**最后更新**：2026-05-05
**目标读者**：后端工程师、Tech Lead、做 ADR 评审的人
**配套**：`docs/PRD.md` · `docs/UI_UX.md` · `docs/CODING_STANDARDS.md` · `docs/adr/`

> 本文档把 Figma 原型「8 屏 + 4 Modal」逐项映射到后端 gap，对每个 gap 给出：涉及包/文件、新增 Protocol/Model、API 端点、依赖、工作量、需要的 ADR、Definition of Done。
>
> 本文档**不写代码**，只规划。后端开干前的最后一道闸门。

---

## 目录

- [0. 范围与约束](#0-范围与约束)
- [1. 总差距热力图（屏 × 后端层）](#1-总差距热力图屏--后端层)
- [2. 横切基础设施（必须先于功能）](#2-横切基础设施必须先于功能)
- [3. 屏幕级 Gap（S1–S8）](#3-屏幕级-gaps1s8)
- [4. Modal/Drawer 级 Gap（M1–M4）](#4-modaldrawer-级-gapm1m4)
- [5. ADR 清单（0009–0019）](#5-adr-清单00090019)
- [6. 优先级与排期](#6-优先级与排期)
- [7. 风险登记](#7-风险登记)
- [8. 延伸（PRD 写了但 prototype 未画）](#8-延伸prd-写了但-prototype-未画)

---

## 0. 范围与约束

**范围**：把后端能力补齐到能驱动 prototype 的「8 屏 + 4 Modal」，并满足 PRD §14.3 D7.1–D7.8 的全部 Exit Criteria。

**不在本文档范围**（写在 §8 延伸）：
- 评测 CI 流水线（GitHub Actions）
- Grafana dashboard
- Operator Runbook
- Security review
- 测试覆盖率提升

**架构约束**（来自 `CODING_STANDARDS.md` 与 PRD §16.6）：
- 模块化单体五层（L1 ingestion / L2 structuring / L3 indexing / L4 retrieval / L5 orchestration）
- 跨 Library 的 Protocol 方法首参 `library_id`，**禁止 `library_ids: list`**（适用 L1–L4）
- L5 编排层允许组合**只读元视图**（详见 PRD §16.6 例外条款）
- 包之间依赖由 `tach` 强制，`tach check` 必须 0 违规
- 所有跨 Library 的领域模型首字段为 `library_id`，并通过 Pydantic validator 拒绝跨库引用

**依赖现状**（来自 2026-05-05 的能力审计）：
- ✅ 已有：Library CRUD、向量检索、BM25、Graph、Community、ReAct、Review/Reason/Hypothesize 同步版、Langfuse、KG 浏览器
- ⊘ 占位：apps/worker（noop）
- ⊘ 缺失：RRF、Rerank、Self-RAG critic、CRAG、ToG、VAR 计算、per-Library 配置覆盖、ZIP/folder 上传、Eval 前端、Activity Log、Notification、Library 状态机、Daily cost cap、Document detail endpoint
- ◐ 部分：Library Export（不含索引）、Library Purge（仅删元数据）

---

## 1. 总差距热力图（屏 × 后端层）

每格颜色含义：🟢 已完整 / 🟡 部分 / 🔴 缺失 / ⚪ 不涉及。

| 屏幕 | L1 ingestion | L2 structuring | L3 indexing | L4 retrieval | L5 orchestration | apps/api | apps/worker | apps/web |
|---|---|---|---|---|---|---|---|---|
| S1 Onboarding | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | 🟢 |
| S2 Library Dashboard | ⚪ | ⚪ | 🟡 stats | ⚪ | 🔴 activity / status / VAR | 🔴 dashboard endpoints | 🔴 status job | 🟡 |
| S3 Chat / QA | ⚪ | ⚪ | ⚪ | 🟡 缺 RRF/Rerank/SelfRAG | 🟡 缺 sessions、缺 trace 暴露 | 🟡 | ⚪ | 🟢 |
| S4 KG Browser | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | 🟢 | ⚪ | 🟢 |
| S5 Review | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 缺结构化进度事件 / 引用风格 | 🟡 缺 cost-estimate API | 🔴 noop | 🟢 |
| S6 Documents | 🟡 缺 ZIP/folder | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | 🔴 noop | 🟢 |
| S7 Reason / Hypothesize | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 缺结构化 path / 三维评分 | 🟡 | 🔴 noop | 🟢 |
| S8 Eval / Settings | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 缺 VAR / KPI 聚合 / per-Library config | 🔴 缺 eval/settings endpoints | 🔴 缺 daily cost / KPI snapshot | 🔴 缺 Eval UI |
| M1 LibraryCreateModal | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 缺 primary_language | ⚪ | 🟢 |
| M2 DeleteConfirmModal | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 缺真实 purge | 🟡 | ⚪ | 🟢 |
| M3 CommandPaletteOverlay | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 缺跨资源搜索 | 🔴 缺 search endpoint | ⚪ | 🟢 |
| M4 DocumentDetailDrawer | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 缺 doc detail endpoint | ⚪ | 🟢 |

**红区集中点**：apps/worker（4 屏依赖）、apps/api 新端点、L5 orchestration 跨库聚合视图、Eval/Settings 体系。

---

## 2. 横切基础设施（必须先于功能）

以下 7 项是 P0 阻塞物，**必须先建起来**才能驱动 §3 / §4 的屏幕功能。

### 2.1 异步任务队列（Arq）

**现状**：`apps/worker/main.py` 是 noop 占位。所有 ingest / KG 抽取 / community / Review / Reason / Hypothesize 都同步跑在 API 进程，长任务直接阻塞请求线程。

**目标**：用 Arq 接入 Redis 作为后端，建立长任务队列；任务可在前端「Run in background」后用户关闭页面，通过任务页或顶栏 Notify 恢复。

**涉及包/文件**：
- `apps/worker/main.py`：替换 noop，注册 Arq `WorkerSettings`
- `apps/worker/jobs/`（新目录）：每类任务一个文件
  - `ingest_document.py`：单 PDF 摄取
  - `ingest_batch.py`：ZIP/folder 批量
  - `extract_kg.py`：NER/RE/EL → Neo4j
  - `rebuild_community.py`：Leiden + 摘要
  - `run_review.py` / `run_reason.py` / `run_hypothesize.py`：长任务
  - `library_status_check.py`：周期性巡检
  - `eval_snapshot.py`：每日 KPI 快照
- `packages/orchestration/task_queue.py`（新）：`TaskQueue` Protocol + Arq 适配器
- `packages/core/models.py`：新增 `TaskSpec`、`TaskHandle`、`TaskState`
- `apps/api/routes/tasks.py`（新）：`GET /v1/libraries/{lib}/tasks`、`GET /v1/libraries/{lib}/tasks/{task_id}`、`POST /v1/libraries/{lib}/tasks/{task_id}/cancel`

**新 Protocol**：

```python
# packages/orchestration/task_queue.py
class TaskQueue(Protocol):
    async def enqueue(
        self, library_id: str, task: TaskSpec, *, priority: int = 0
    ) -> TaskHandle: ...
    async def get(self, library_id: str, task_id: str) -> TaskState | None: ...
    async def cancel(self, library_id: str, task_id: str) -> bool: ...
    async def list_active(self, library_id: str) -> list[TaskHandle]: ...
```

**新模型**：

```python
class TaskSpec(BaseModel):
    library_id: str
    task_type: Literal["ingest", "kg_extract", "community_rebuild",
                       "review", "reason", "hypothesize", "eval"]
    input: dict
    budget: RetrievalBudget | None = None

class TaskState(BaseModel):
    library_id: str
    task_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float       # 0.0 – 1.0
    current_stage: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result_pointer: str | None  # MinIO key 或 Postgres row id
```

**ADR**：**ADR-0009 异步任务队列选型** — Arq vs Temporal vs FastAPI BackgroundTasks vs Celery。建议 Arq（已有 Redis 依赖、轻量、Python 原生异步、与 FastAPI 风格一致；Temporal 过重，Celery 配置笨）。

**工作量**：L（1.5–2 周）。

**DoD**：
- 提交 Review 任务后 API 立刻返回 `task_id`，前端可关闭页面
- 任务在 Worker 跑完后状态写回 Postgres
- 重启 Worker 不丢任务（Arq 持久化）
- 任务可取消

---

### 2.2 SSE 任务进度事件协议

**现状**：现有 review/reason/hypothesize 端点支持 SSE，但只吐 token 流；Pipeline tree（S5）所需的「子主题切分完成 / 第 3 子主题正在召回」之类的结构化阶段事件**没有**。

**目标**：定义统一的 `TaskEvent` 协议，所有长任务都按此结构化吐进度，前端据此渲染 Pipeline Tree、citations 实时列表、cost 仪表。

**涉及包/文件**：
- `packages/orchestration/events.py`（新）：`TaskEvent` 模型与 `TaskEventBus` Protocol
- `apps/api/routes/sse.py`（新或合并到现有任务 route）：从 Redis pub/sub 读 → SSE
- `packages/observability/`：扩展 Langfuse adapter，让每个 stage 也是一个 trace span

**新模型**：

```python
class TaskEvent(BaseModel):
    library_id: str
    task_id: str
    seq: int                 # 严格递增，前端用于乱序重组
    timestamp: datetime
    type: Literal[
        "task_queued", "task_started",
        "stage_started", "stage_progress", "stage_completed",
        "token", "citation_added",
        "cost_updated",
        "task_completed", "task_failed", "task_cancelled",
    ]
    stage_name: str | None = None
    payload: dict = {}
```

**典型 payload**：
- `stage_started`: `{"stage": "subtopic_decompose", "estimated_duration_s": 8}`
- `stage_progress`: `{"stage": "subtopic_local_search", "current": 3, "total": 5}`
- `citation_added`: `{"chunk_id": "...", "rank": 7, "source": "vector"}`
- `cost_updated`: `{"tokens_in": 1024, "tokens_out": 512, "cost_usd": 0.0034}`

**ADR**：**ADR-0010 SSE 任务进度事件协议** — 含事件类型枚举的稳定性约定（不许随意加），跨任务复用。

**工作量**：M（4–5 天，需要重构现有 review SSE）。

**DoD**：
- 综述任务跑完后，前端能按 `stage_started/completed` 重建出 Pipeline Tree
- `citation_added` 事件能驱动右侧 Live citations 实时增长
- 每条 `cost_updated` 都能更新 Composer/任务页 cost 显示
- 事件丢失不破坏：前端拿到 `seq` 不连续可重连补拉

---

### 2.3 通知中心 / Outbox

**现状**：没有「任务完成 / 告警 / 配额触顶」的事件通道。

**目标**：所有面向用户的事件落 Postgres `notifications` 表；前端用 SSE 长连接订阅；浏览器关闭再回来能拉历史未读。

**涉及包/文件**：
- 新表 `notifications` 在 Postgres
- `packages/core/models.py`：新增 `Notification`
- `apps/api/routes/notifications.py`（新）：`GET /v1/notifications?unread=1&since=...`、`POST /v1/notifications/{id}/read`
- Worker 任务在终态写一条；library_status_check 在状态变化时写一条；alert 引擎在告警时写一条

**新模型**：

```python
class Notification(BaseModel):
    id: str
    library_id: str | None    # None 表示全局（如 worker 离线）
    type: Literal[
        "task_completed", "task_failed",
        "ingest_completed", "ingest_failed",
        "library_status_changed", "alert_triggered",
        "daily_cost_warning", "daily_cost_blocked",
    ]
    severity: Literal["info", "warning", "danger"]
    title: str
    body: str | None
    payload: dict
    read: bool = False
    created_at: datetime
```

**ADR**：**ADR-0011 通知中心存储与传输** — 选择 Postgres 表 + SSE pull，而非 Redis Streams 或 WebSocket（理由：v1 用户量小、Postgres 对未读状态/历史更友好）。

**工作量**：S（2–3 天）。

**DoD**：
- Review 任务结束 30 秒内顶栏 Notify 红点出现
- 用户关页面 5 分钟回来，未读历史还在
- Library 状态从 Indexing → Healthy 时有一条 info 通知

---

### 2.4 per-Library 配置存储与读取

**现状**：全局 `Settings` 唯一；没有 Library 级覆盖。

**目标**：每个 Library 可独立配置 LLM 路由 / Embedder / 检索预算 / 每日成本上限；未覆盖项继承全局默认。

**涉及包/文件**：
- 新表 `library_config`
- `packages/core/models.py`：`LibraryConfig` 模型
- `packages/core/library_admin.py`：`get_config(library_id)` / `update_config(library_id, patch)`
- `packages/llm/gateway.py`：路由前先 `get_config` 取 override
- `packages/embedding/service.py`：同上
- `packages/orchestration/budget.py`：检索预算读 per-Library
- `apps/api/routes/library_settings.py`（新）：`GET/PUT /v1/libraries/{lib}/settings`

**新模型**：

```python
class LibraryConfig(BaseModel):
    library_id: str
    llm_router_override: LLMRouterSpec | None = None
    embedder_override: EmbedderSpec | None = None
    retrieval_budget_override: RetrievalBudget | None = None
    daily_cost_cap_usd: Decimal | None = None
    schema_yaml_path: str | None = None
    updated_at: datetime

class LLMRouterSpec(BaseModel):
    primary: str            # e.g. "claude-haiku-4-5"
    fallback: list[str]     # ordered fallback chain
    prefer_local: bool

class EmbedderSpec(BaseModel):
    name: str               # "bge-m3" / "openai-3-large"
    dim: int
```

**新 Protocol**：

```python
class LibraryConfigStore(Protocol):
    async def get(self, library_id: str) -> LibraryConfig: ...
    async def update(self, library_id: str, patch: LibraryConfigPatch) -> LibraryConfig: ...
```

**ADR**：**ADR-0012 per-Library 配置覆盖** — 阐述：JSONB 列 vs 平铺列（选 JSONB，schema 演进无 migration 痛苦）；override 语义（None = 继承）；切换 Embedder 后是否 force 重建索引（v1 不做，前端给警告）。

**工作量**：M（1 周）。

**DoD**：
- `/v1/libraries/{lib}/settings` 可读写
- 切换某 Library LLM router 后，对该库的 QA / Review 调用确实路到新模型
- 全局默认值变化时，未 override 的 Library 自动生效

---

### 2.5 Library 状态机

**现状**：Library 没有状态字段，UI 上的「Healthy / Indexing / Stale community」三态没有数据来源。

**目标**：每个 Library 有 `status` 字段，由周期性巡检 job 维护；状态变化触发 Notification。

**涉及包/文件**：
- `libraries` 表加列：`status TEXT NOT NULL DEFAULT 'healthy'`、`status_updated_at TIMESTAMPTZ`
- `packages/core/models.py`：`Library` 模型加 `status`
- `apps/worker/jobs/library_status_check.py`（新）：每 5 min 扫一次
- 状态判定逻辑：
  - 任意活跃 ingest / KG / community 任务 → `Indexing`
  - 最后一次 community rebuild > 7 天 且 自上次 rebuild 后新增文档 ≥ 50 → `Stale community`
  - 其他 → `Healthy`

**新模型**：

```python
class LibraryStatus(StrEnum):
    HEALTHY = "healthy"
    INDEXING = "indexing"
    STALE_COMMUNITY = "stale_community"

class Library(BaseModel):
    library_id: str
    name: str
    description: str | None
    primary_language: Literal["en", "zh", "mixed"] = "en"
    status: LibraryStatus = LibraryStatus.HEALTHY
    status_updated_at: datetime
    created_at: datetime
```

**ADR**：**ADR-0013 Library 状态机** — 状态转移图、判定阈值（7 天、50 篇是否合理）、与 Notification 的耦合方式。

**工作量**：S（2–3 天）。

**DoD**：
- 灌入 60 篇新文档 + 不跑 community rebuild 7+ 天后，状态自动变 Stale community 并发通知
- 状态变化在 S2 卡片徽章上 ≤ 5 min 反映

---

### 2.6 Activity Log（L5 编排层跨库聚合）

**现状**：S2 Recent Activity 时间线没有数据源。

**目标**：所有重要事件落 `activity_log` 表；S2 端点可跨用户拥有的所有 Library 拉聚合时间线。

**涉及包/文件**：
- 新表 `activity_log`，按月 `library_id` 分区
- `packages/orchestration/activity.py`（新）：`ActivityLogger` Protocol + `record(event)` helper
- 各任务终态在 worker 里调用 `activity.record(...)`
- `apps/api/routes/activity.py`（新）：`GET /v1/activity?library_ids[]=a&library_ids[]=b&limit=50`

**关键违反点说明**：此端点接受 `library_ids: list`，违反 PRD §16.6「Protocol 方法不接受 list」原则。**根据 §16.6 例外条款**，这只允许在 L5 编排层（apps/api 路由），数据底层 Protocol 仍然 per-library_id。`ActivityLogger.record` 仍只接受单 `library_id`；list 拼合发生在 SQL 层。

**新模型**：

```python
class ActivityEvent(BaseModel):
    id: int
    library_id: str
    type: Literal[
        "ingest_completed", "ingest_failed",
        "kg_extracted",
        "community_rebuilt",
        "review_completed", "reason_completed", "hypothesize_completed",
        "library_purged",
    ]
    title: str
    summary: str | None
    payload: dict
    created_at: datetime
```

**ADR**：**ADR-0014 Activity Log 设计** — 说明 §16.6 例外的具体边界（什么算"只读元视图"），分区策略，保留期（建议 90 天）。

**工作量**：S（2 天）。

**DoD**：
- S2 Recent Activity 真实展示混合 Library 的事件流
- 单 Library 视图的 Activity 也复用同一表（带 `library_id` 单值过滤）

---

### 2.7 per-Library Daily Cost 统计与上限

**现状**：Langfuse 统计 LLM 成本，但没有 per-Library / per-day 聚合，也没有上限拦截。

**目标**：每条 LLM 调用按 `library_id` + `date` 累加；超 `daily_cost_cap_usd` 后阻断新任务并通知。

**涉及包/文件**：
- 新表 `library_daily_cost`：`(library_id, date, cost_usd)` 主键
- `packages/llm/gateway.py`：每次响应后写一行（upsert 累加）；调用前检查上限
- `packages/orchestration/budget.py`：硬阻断逻辑
- `apps/api/routes/library_settings.py`：暴露今日累计成本

**ADR**：**ADR-0015 Daily Cost Cap 拦截策略** — 软警告 vs 硬阻断阈值（建议 80% warn / 100% block）；阻断生效粒度（任务级 vs 单次 LLM 调用级）；与 Notification 的联动。

**工作量**：S（2 天）。

**DoD**：
- 跑到 80% 时顶栏 Notify warning
- 跑到 100% 后新建任务直接拒绝并返回明确错误码

---

## 3. 屏幕级 Gap（S1–S8）

### 3.1 S1 Onboarding

**Prototype 行为**：`GET /v1/libraries` 返回空数组时显示欢迎页、3 步骤、CTA「Create your first Library」。

**后端 Gap**：✅ 无新增 — 已有 Library list endpoint 即可。

**DoD**：手动清空 libraries 表后访问根路径，前端正确展示 Onboarding。

---

### 3.2 S2 Library Dashboard

**Prototype 行为**：4 张 Library 卡（含 docs/chunks/entities/triples 计数 + 状态徽章）、Recent Activity 列表、Quality KPI 面板（VAR/Citation F1/P95/cost）。

**Gap 1：Library Stats 计数 endpoint**

- 现状：单条 Library 计数没有专用端点（前端要拼 4 个 endpoint）
- 文件：`apps/api/routes/libraries.py` 加 `GET /v1/libraries/{lib}/stats`
- 返回：`{"docs": int, "chunks": int, "entities": int, "triples": int, "communities": int, "community_freshness_days": int}`
- 涉及：`packages/indexing/coordinator.py` 暴露 `get_stats(library_id)` 聚合调用 4 个适配器
- 工作量：S（1 天）

**Gap 2：Library 状态徽章数据源**

- 见 §2.5 Library 状态机

**Gap 3：Recent Activity 数据源**

- 见 §2.6 Activity Log

**Gap 4：Quality KPI 面板（含 VAR）**

- 现状：VAR 不计算；其他指标分散在 Langfuse；没有聚合 endpoint
- 涉及：
  - `packages/evaluation/var.py`（新）：`compute_var(library_id, *, eval_set, days)` — 默认从 smoke set + 用户反馈算
  - `apps/api/routes/eval.py`（新）：`GET /v1/libraries/{lib}/eval/kpis?eval_set=smoke&days=7`
  - 返回：`{"var": 0.764, "citation_f1": 0.872, "p95_latency_s": 14.2, "avg_cost_usd": 0.084, "delta": {...}}`
- 数据源：
  - VAR：用户反馈（feedback table）+ smoke set 自动跑
  - Citation F1：现有 `packages/evaluation/`
  - P95 / cost：Langfuse query
- 新模型：`AnswerFeedback`（用户对答案的标记，详见 §3.3 Gap 5）
- 工作量：M（1 周，含 VAR 反馈 endpoint）
- ADR：**ADR-0016 VAR 计算口径** — 「用户标记 useful + correct citation」 vs 「LLM-judge auto-score」 vs 两者加权；smoke set 是否每日自动跑

**Gap 5：Library filter for KPI panel**

- 现状：dashboard 有跨库 KPI 总览
- 涉及：`/v1/eval/kpis-summary?library_ids[]=a&library_ids[]=b` 同 §2.6 例外条款
- 工作量：S（半天）

---

### 3.3 S3 Chat / QA（旗舰）

**Prototype 行为**：流式答案 + 引用 chip + 内联 reasoning trace 展开 + 斜杠命令 + 多轮会话列表 + Composer（Library pill / Model selector / Budget pill / Send）+ 右侧 Evidence Panel。

**Gap 1：Reasoning Trace 内联暴露**

- 现状：`packages/retrieval/strategies/react_rag.py` 跑完后 `RetrievalTrace` 落 Langfuse，但**没有以前端可读形式回到响应里**
- 目标：`AnsweredQuery` 多带一个 `trace: RetrievalTrace`（或链接到 Langfuse 的 deep-link）
- 文件：
  - `packages/core/models.py`：`AnsweredQuery` 加 `trace: RetrievalTrace | None`
  - `packages/orchestration/qa.py`：把 trace 透传到响应
  - SSE：每个 retrieval step 发 `stage_progress` 事件（见 §2.2）
- 工作量：S（2–3 天）

**Gap 2：Self-RAG critic / CRAG 评估器 / ToG 多跳**

- 现状：只有基础 ReAct
- 目标：补齐 PRD §11.2 列出的 4 种 strategy
- 文件（全部新建）：
  - `packages/retrieval/strategies/self_rag_critic.py`：prompt-based 反思（4 reflection token 类型）
  - `packages/retrieval/strategies/crag_evaluator.py`：cross-encoder 打分阈值，低分触发重检索
  - `packages/retrieval/strategies/tog_planner.py`：KG beam search（depth ≤ 3, beam ≤ 4）
  - `packages/retrieval/rewriter.py`：HyDE / Step-Back / decompose
- 新 Protocol：

```python
class RetrievalStrategy(Protocol):
    name: str
    async def run(
        self, library_id: str, query: Query, budget: RetrievalBudget
    ) -> RetrievalTrace: ...
```

- API：`POST /v1/libraries/{lib}/qa` 接受 `strategy: "react" | "self_rag" | "crag" | "tog" | "auto"`
- 工作量：L（2–3 周，多种策略 + 评测对比）
- ADR：**ADR-0017 Self-RAG 实现路径** — 用 prompt-based（不改词表）vs fine-tune 路线；与 ReAct 怎么编排（串联 / 并联 / 路由）

**Gap 3：RRF + Rerank**

- 现状：HybridRetrievalCoordinator 没真正多路并行 + 融合
- 文件：
  - `packages/indexing/fusion.py`（新）：`reciprocal_rank_fusion(runs, k=60) → ranked_list`
  - `packages/indexing/reranker.py`（新）：BGE-reranker-v2 适配器
  - `packages/indexing/coordinator.py`：改为 vector + bm25 + graph 三路并行 → RRF → Rerank top-K → 返回
- 新 Protocol：

```python
class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: list[RetrievedEvidence]
    ) -> list[RetrievedEvidence]: ...
```

- 工作量：M（5–7 天）
- ADR：**ADR-0018 Reranker 选型** — BGE-reranker-v2 vs Cohere Rerank API vs 不做；rerank 阈值；is library_id 透传必要（reranker 本身 library 无关）

**Gap 4：多轮会话列表**

- 现状：M8 加了 conversations API，但前端只用 `answer` / `answer_in_conversation` 两条路径，不暴露会话列表
- 文件：
  - `apps/api/routes/conversations.py`（已存在或新建）：`GET /v1/libraries/{lib}/conversations?limit=20`
  - 返回：`[{conversation_id, title, last_message_preview, updated_at, message_count}, ...]`
- 工作量：S（2 天）

**Gap 5：用户反馈 endpoint**

- 现状：用户标记答案 useful / 引用正确，没有 endpoint
- 文件：
  - `packages/core/models.py`：`AnswerFeedback`
  - 新表 `answer_feedback`
  - `apps/api/routes/qa.py` 加 `POST /v1/libraries/{lib}/qa/{answer_id}/feedback`
- 模型：

```python
class AnswerFeedback(BaseModel):
    library_id: str
    answer_id: str
    user_id: str | None
    useful: bool
    citations_correct: bool
    comment: str | None
    created_at: datetime
```

- 与 §3.2 Gap 4 配合，VAR 算得出来
- 工作量：S（1 天）

**Gap 6：Empty State**

- 现状：0 命中检索时仍走 LLM 拼答案
- 文件：`packages/retrieval/coordinator.py` 加阈值检查；命中 0 → 返回特殊响应 `{"empty": true, "reason": "no_evidence", "suggestions": [...]}`
- 工作量：S（半天）

**Gap 7：斜杠命令**

- 现状：纯前端逻辑（Composer 解析 `/review` 跳到 `/lib/:id/review`）
- 后端 Gap：无新增（已有任务端点）
- DoD：前端集成测试覆盖

---

### 3.4 S4 KG Browser

**Prototype 行为**：6 类型过滤 chip、深度滑杆 1–3、confidence 阈值、Cytoscape 力导向、实体详情抽屉。

**Gap 1：实体类型 ontology 落地**

- 现状：`docs/ontology/` 有 schema YAML，但实体到 6 类的映射可能不一致
- 文件：核对 `docs/ontology/<library_id>/v1.yaml` 是否含 `Concept / Method / Dataset / Metric / Author / Venue`
- 工作量：XS（半天）

**Gap 2：邻域 endpoint 支持类型 / 深度 / confidence 参数**

- 现状：`GET /v1/libraries/{lib}/entities/{eid}/neighborhood` 已存在
- 需要：query 支持 `?types=Concept,Method&depth=2&min_confidence=0.65&limit=50`
- 文件：`apps/api/routes/entities.py` 增加参数；`packages/indexing/graph_index.py` 增加过滤
- 工作量：S（1–2 天）

---

### 3.5 S5 Review Generation

**Prototype 行为**：配置（年份 / 字数 / 子主题 chip / 引用风格）→ cost 估算 → Run / Run in bg → 进入任务页：左侧 Pipeline Tree + 中部流式 markdown + 右侧 Live citations + 底部 cost。

**Gap 1：Cost 估算 endpoint**

- 现状：`ReviewGenerationTask` 无 dry-run 模式
- 文件：
  - `packages/orchestration/tasks/review.py`：加 `estimate_cost(library_id, input) -> CostEstimate`
  - `apps/api/routes/review.py`：`POST /v1/libraries/{lib}/review/estimate`
- 模型：`CostEstimate(estimated_tokens_in, estimated_tokens_out, estimated_cost_usd, estimated_duration_s)`
- 工作量：S（1–2 天）

**Gap 2：Pipeline Tree 进度事件**

- 见 §2.2 SSE 协议；review task 实现需在每个阶段调 `event_bus.emit(stage_started/...)`
- 工作量：M（重构现有 review，3–4 天）

**Gap 3：引用风格选择**

- 现状：`ReviewGenerationTask` 输出固定格式
- 文件：`review.py` input 加 `citation_style: Literal["numeric", "author_year"]`，output 渲染分支
- 工作量：S（1 天）

**Gap 4：后台运行 + 任务恢复**

- 见 §2.1 + §2.3
- DoD：用户点 Run in bg → 关页面 → 5 min 后回访任务页能看到完整结果

---

### 3.6 S6 Documents

**Prototype 行为**：拖拽上传 PDF / ZIP / folder；表格行展示 5 态（Queued / Parsing / Indexing / Ready / Failed）；Failed 显示错误详情 popover + Retry；点行打开 DocumentDetailDrawer。

**Gap 1：ZIP / folder 上传**

- 现状：仅单 PDF
- 文件：
  - `apps/api/routes/ingest.py`：multipart 接受 ZIP / 多 file
  - `packages/ingestion/extractor.py`（新）：`extract_zip(path) -> list[Path]`、`walk_folder(path) -> list[Path]`
  - 在 worker 里：`ingest_batch` job 展开后排队 N 个 `ingest_document` 子任务
- 新 Protocol：

```python
class BatchIngestor(Protocol):
    async def ingest_zip(self, library_id: str, zip_path: Path) -> list[TaskHandle]: ...
    async def ingest_folder(self, library_id: str, folder_path: Path) -> list[TaskHandle]: ...
```

- 工作量：M（4–5 天，含 sandbox 解压安全）
- ADR：**ADR-0019 ZIP/folder 上传管线** — 解压沙箱、最大文件数、防 zip-bomb

**Gap 2：5 态状态机**

- 现状：状态散落，没有统一模型
- 文件：
  - `packages/core/models.py`：`Document` 加 `ingest_status: Literal["queued","parsing","indexing","ready","failed"]`、`ingest_error: str | None`、`ingest_progress: float`
  - 各 worker job 在 stage 边界更新 status
- 工作量：S（2 天）

**Gap 3：失败重试**

- 文件：`apps/api/routes/ingest.py` 加 `POST /v1/libraries/{lib}/docs/{doc_id}/retry?parser=mineru`
- 工作量：S（1 天）

**Gap 4：错误详情**

- 文件：`Document.ingest_error` 含结构化错误（错误码 + suggestion）
- 错误模型：`IngestError(code: str, message: str, suggestion: str | None)`
- 工作量：S（1 天）

---

### 3.7 S7 Reason + Hypothesize

**Gap 1：Reason 返回结构化 path**

- 现状：返回纯文本
- 文件：
  - `packages/core/models.py`：新增 `ReasoningPath`、`ReasoningResult`
  - `packages/orchestration/tasks/reason.py`：返回结构化 path 列表
- 模型：

```python
class ReasoningPath(BaseModel):
    library_id: str
    nodes: list[Entity]            # 同 library_id 校验
    relations: list[Triple]
    confidence: float
    rationale: str                 # LLM-generated narrative

class ReasoningResult(BaseModel):
    library_id: str
    question: str
    answer: str
    paths: list[ReasoningPath]
    citations: list[Citation]
    duration_ms: int
```

- 工作量：M（4 天）

**Gap 2：Hypothesize 三维评分**

- 现状：只生成假设文本，无评分
- 文件：
  - `packages/orchestration/tasks/hypothesis.py`：`score_hypothesis(library_id, candidate) -> ScoreVector`
  - 实现：
    - `novelty`：candidate embedding vs 现有结论 embedding 平均距离（高 = 远 = 新）
    - `confidence`：`geomean(path.confidence for path in candidate.paths)`
    - `verifiability`：路径上 Method / Dataset 节点比例 × 经验系数
- 模型：

```python
class HypothesisCandidate(BaseModel):
    library_id: str
    text: str
    novelty: float           # [0,1]
    confidence: float        # [0,1]
    verifiability: float     # [0,1]
    paths: list[ReasoningPath]
    evidence: list[Citation]
```

- 排序：`sort_key = novelty × confidence`
- 工作量：M（5 天，需要校准）
- ADR：**ADR-0020 Hypothesis 评分公式** — 三维定义、权重、与 PRD §12.3 D5.3 验收对齐

---

### 3.8 S8 Eval + Settings

**Gap 1：Eval KPI / 趋势 / 失败 case endpoints**

- 文件：
  - `apps/api/routes/eval.py`（新）：
    - `GET /v1/libraries/{lib}/eval/kpis?eval_set=smoke&days=7`
    - `GET /v1/libraries/{lib}/eval/trend?metric=var&days=30&granularity=day`
    - `GET /v1/libraries/{lib}/eval/failures?limit=20&days=30`
  - `packages/evaluation/snapshot.py`（新）：每日快照 job，写入 `eval_snapshots` 表
- 新表：`eval_snapshots(library_id, date, metric, value, eval_set)`
- Worker job：`apps/worker/jobs/eval_snapshot.py` cron 每天 02:00 跑
- 工作量：M（1 周）

**Gap 2：VAR 告警引擎**

- 现状：无
- 文件：
  - `packages/evaluation/alerts.py`（新）：周环比下跌 > 5pp 触发
  - 触发后：写 Notification + 写 `alerts` 表（带状态 active/recovered）
- 工作量：S（2 天）
- ADR：**ADR-0021 Eval 告警规则** — 阈值、触发频率、自动恢复条件

**Gap 3：Settings endpoints**

- 见 §2.4 per-Library 配置存储
- API：`GET/PUT /v1/libraries/{lib}/settings` 已在 §2.4 列入

**Gap 4：Eval 前端**

- 现状：审计明确「无前端评测面板」
- 文件：`apps/web/src/views/EvalView.vue`（新）+ 子组件
- 工作量：M（1 周）— 不在本 roadmap 严格范围（前端），但列出以提醒

---

## 4. Modal/Drawer 级 Gap（M1–M4）

### 4.1 M1 LibraryCreateModal

**已有**：`POST /v1/libraries`

**Gap 1：primary_language 字段**

- 文件：`packages/core/models.py` `Library` 加 `primary_language`
- 迁移：libraries 表加列
- 工作量：XS（半天）

**Gap 2：slug 校验**

- 现状：可能未严格校验
- 文件：`Library` Pydantic validator `pattern=r"^[a-z][a-z0-9-]{2,30}$"`
- 工作量：XS

---

### 4.2 M2 DeleteConfirmModal

**Gap：真正的 purge**

- 现状：只删 metadata；Qdrant collection / Neo4j DB / BM25 index / MinIO prefix 残留
- 文件：
  - `packages/core/library_admin.py`：`purge_library(library_id)` 必须串行调每个适配器的 `purge_library`
  - 各适配器 `purge_library` 实现：
    - `packages/indexing/qdrant_adapter.py`：`client.delete_collection(f"chunks_{library_id}")`
    - `packages/indexing/neo4j_adapter.py`：`DROP DATABASE` 或清空 label
    - `packages/indexing/bm25_adapter.py`：`index.delete()`
    - `packages/indexing/minio_adapter.py`：`remove_objects(prefix=f"{library_id}/")`
    - Postgres：`DELETE FROM ... WHERE library_id = ?` for 各表
- API：`DELETE /v1/libraries/{lib}?purge=1` 走真 purge 路径
- 写 `library_purged` activity log
- 工作量：M（4 天 — 多适配器，需要回滚机制）
- ADR：**ADR-0022 Library Purge 原子性** — 多存储跨边界事务保证（部分失败时怎么处理：retry / mark partial / 提示运维）

---

### 4.3 M3 CommandPaletteOverlay

**Gap：跨资源 search endpoint**

- 现状：无
- 文件：`apps/api/routes/search.py`（新）`GET /v1/search?q=...&library_id=current&types=entity,document,library,action&limit=20`
- 实现：
  - 切词 + 并行查
    - `entity`：Neo4j name + alias fuzzy（限定 library）
    - `document`：BM25 标题（限定 library）
    - `library`：Postgres ILIKE on `name`/`description`（跨库，因为 ⌘K 也用于切库）
    - `action`：静态注册表（"Open Chat", "Generate Review", ...）
- 返回：

```python
class SearchHit(BaseModel):
    type: Literal["entity", "document", "library", "action"]
    id: str
    title: str
    subtitle: str | None
    library_id: str | None       # action / library 类型可为 None
    score: float
```

- 工作量：M（4 天）
- ADR：**ADR-0023 ⌘K 跨资源搜索** — 跨库搜索 library 名是否破坏 §16.6（结论：library 元数据本就不属于"数据"，类比 file system 的 directory listing，明确写入例外条款）

---

### 4.4 M4 DocumentDetailDrawer

**Gap：document detail endpoint**

- 现状：无
- 文件：`apps/api/routes/documents.py`（新或扩展）：
  - `GET /v1/libraries/{lib}/docs/{doc_id}` 返回 `DocumentDetail`
  - `GET /v1/libraries/{lib}/docs/{doc_id}/chunks?section=4.5&limit=20`
  - `GET /v1/libraries/{lib}/docs/{doc_id}/pdf` 返回 MinIO presigned URL
- 模型：

```python
class Section(BaseModel):
    library_id: str
    doc_id: str
    section_path: str          # "4.5" / "Abstract"
    title: str
    page: int

class DocumentDetail(BaseModel):
    doc: Document
    sections: list[Section]
    chunks_count: int
    entities_count: int
    triples_count: int
    pages_count: int
```

- 工作量：M（3–4 天，含 PDF preview signed URL 接入）

---

## 5. ADR 清单（0009–0023）

| # | ADR | 决策点 | 优先级 |
|---|---|---|---|
| 0009 | 异步任务队列选型 | Arq / Temporal / FastAPI BG / Celery | P0 |
| 0010 | SSE 任务进度事件协议 | 事件类型枚举的稳定性约定 | P0 |
| 0011 | 通知中心存储与传输 | Postgres + SSE pull / Redis Streams / WebSocket | P0 |
| 0012 | per-Library 配置覆盖 | JSONB 列 vs 分表；切 Embedder 重建索引策略 | P1 |
| 0013 | Library 状态机 | 三态判定阈值与转移图 | P1 |
| 0014 | Activity Log 设计 | §16.6 例外的具体边界、分区、保留期 | P1 |
| 0015 | Daily Cost Cap 拦截策略 | 软警告 / 硬阻断阈值；阻断粒度 | P1 |
| 0016 | VAR 计算口径 | feedback / LLM-judge / 加权 | P1 |
| 0017 | Self-RAG 实现路径 | prompt-based / fine-tune；与 ReAct 编排 | P1 |
| 0018 | Reranker 选型 | BGE-reranker-v2 / Cohere / 不做 | P1 |
| 0019 | ZIP/folder 上传管线 | 沙箱、最大文件数、防 zip-bomb | P2 |
| 0020 | Hypothesis 评分公式 | 三维定义与权重 | P2 |
| 0021 | Eval 告警规则 | 阈值、触发频率、自动恢复 | P2 |
| 0022 | Library Purge 原子性 | 跨存储事务保证 | P0 |
| 0023 | ⌘K 跨资源搜索边界 | library 元数据搜索是否破坏 §16.6 | P2 |

---

## 6. 优先级与排期

### P0 — Critical Path（不做无法上 M7）

按依赖顺序：

1. **ADR-0009 + 任务队列**（§2.1） — 阻塞 4 屏（S2/S5/S6/S7）
2. **ADR-0010 + SSE 事件**（§2.2） — 阻塞 S5（Pipeline Tree）+ S6（进度条）
3. **ADR-0011 + 通知中心**（§2.3） — 阻塞「Run in bg」UX 闭环
4. **ADR-0022 + 真 Purge**（§4.2） — 安全红线
5. Reasoning Trace 暴露（§3.3 Gap 1） — Trust through Trace 原则的支撑

**预估**：3–4 周（1 人）

### P1 — M7 收口必须

6. ADR-0012 + per-Library 配置（§2.4）
7. ADR-0013 + Library 状态机（§2.5）
8. ADR-0014 + Activity Log（§2.6）
9. ADR-0015 + Daily Cost Cap（§2.7）
10. ADR-0016 + VAR 计算 + 用户反馈（§3.2 Gap 4 + §3.3 Gap 5）
11. ADR-0017 + Self-RAG critic（§3.3 Gap 2）
12. ADR-0018 + RRF/Rerank（§3.3 Gap 3）
13. Eval endpoints + 告警引擎（§3.8 Gap 1+2）
14. 真 Library Stats endpoint（§3.2 Gap 1）
15. Document Detail endpoint（§4.4）
16. ⌘K Search endpoint（§4.3）
17. ZIP/folder 上传（§3.6 Gap 1）
18. Reason 结构化 path（§3.7 Gap 1）

**预估**：5–6 周（1 人）

### P2 — M7 nice-to-have（可滑到 v1.1）

19. ADR-0020 + Hypothesis 三维评分（§3.7 Gap 2）
20. CRAG / ToG（§3.3 Gap 2 后半）
21. 引用风格选择（§3.5 Gap 3）
22. Eval 前端 EvalView.vue（§3.8 Gap 4）

**预估**：2–3 周（1 人）

### 总周期

- 单人全职：**10–13 周**
- 双人并行（一人主基础设施、一人主功能）：**6–8 周**
- 关键路径：ADR-0009 队列必须最先拍板（影响所有任务设计）

---

## 7. 风险登记

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| BR01 | Arq 在我们 workload 下不够稳（任务丢失/重复） | 中 | 高 | 早期做压测；预留 Temporal 切换路径；Arq job 设计为幂等 |
| BR02 | SSE 事件协议早期定不全，后期反复改 | 高 | 中 | ADR-0010 落实前先做 1 个屏（Review）打样；版本化事件 schema |
| BR03 | per-Library 切 Embedder 后旧索引不可用，用户困惑 | 中 | 中 | UI 拦截 + warning；切 Embedder 时强制 reindex 任务 |
| BR04 | VAR 反馈样本少导致指标抖动 | 高 | 中 | 早期靠 LLM-judge 兜底；明确告知用户「样本数 < N 时指标仅供参考」 |
| BR05 | 跨存储 purge 部分失败 | 中 | 高 | ADR-0022 设计 idempotent + retry；purge 失败状态可重试 |
| BR06 | RRF/Rerank 性能拖累 P95 | 中 | 中 | rerank 仅 top-30；超时降级回 RRF-only；持续监控 P95 |
| BR07 | Self-RAG 反思导致 LLM 调用翻 3-5 倍，成本爆 | 高 | 高 | 预算硬阻断 + per-Library cost cap；strategy=auto 默认走最便宜路径 |
| BR08 | Activity Log 写入压力大 | 低 | 中 | 异步写入；按月分区 |
| BR09 | KG embedding 提取在大 Library 上 OOM | 中 | 高 | 分批处理；worker 单任务内存上限；M2 的 schema 校验防止失控扩张 |
| BR10 | ⌘K 搜索 N+1 慢 | 中 | 中 | 4 个查询并行；超时单独 source 降级；前端 200ms debounce |

---

## 8. 延伸（PRD 写了但 prototype 未画）

以下不在本 roadmap 严格范围，但 PRD 已要求，写在这里以提醒后续排期。

### 8.1 评测 CI 流水线

- PRD §13 / §16.2 要求每次 PR 跑 smoke set 并贴 PR 评论
- 文件：`.github/workflows/eval-on-pr.yml`（新）
- 工作量：S（2 天）

### 8.2 Grafana Dashboard

- PRD §13 / §16.3 要求 VAR / Citation F1 / P95 / cost 上 Grafana
- 文件：`infra/grafana/dashboards/*.json`
- 工作量：S（2 天，假设 Prometheus 已采集）

### 8.3 Operator Runbook

- PRD §14.2 / §14.4 要求 Runbook 含 10 个常见故障排查步骤
- 文件：`docs/OPERATOR_RUNBOOK.md`（已存在，需补全）
- 工作量：M（持续，每出一个生产事件补一条）

### 8.4 Security Review

- PRD §16.4 / §14.4 要求 M7 前完成 `security-review` agent 审查
- 工作量：S（半天 agent 跑 + 1 天修关键 finding）

### 8.5 测试覆盖率提升

- PRD §3.2 + 各 milestone Exit 要求 ≥ 80%
- 当前缺测试的部分：worker jobs、跨存储 purge、SSE 协议、per-Library config
- 工作量：随功能并行（每个 PR 自带测试）

### 8.6 ZH / EN 双语 i18n key 校验

- PRD §14.2 要求 CI 校验 zh/en key 集合一致
- 文件：`apps/web/scripts/check-i18n.ts`、CI workflow
- 工作量：S（1 天）

---

## 收尾

**Definition of Done for entire M7**：

- [ ] 所有 §6 P0 + P1 项完成
- [ ] PRD §14.4 Exit Criteria 全部 ✅
- [ ] 5 位 α 测试用户 VAR ≥ 70%
- [ ] 8 屏 + 4 Modal 端到端 Playwright 测试通过
- [ ] `tach check` 0 违规
- [ ] 测试覆盖率 ≥ 80%
- [ ] 新增 15 个 ADR（0009–0023）全部 merged
- [ ] 没有 P0/P1 bug 未修

**第一步建议**：抓 ADR-0009（任务队列）和 ADR-0010（SSE 事件）先评审拍板；这两条决定了 P0 的所有后续工作。建议先开 4 小时设计会议出这两个 ADR 的初稿。

---

**END**
