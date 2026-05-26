# ADR-0014: Activity Log and L5 Cross-Library Aggregation Boundary

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M7 D7.1（Library Dashboard Recent Activity）；BACKEND_ROADMAP §2.6
**Related**: ADR-0003（Library as Data Partition）；ADR-0011（Notification Center）；ADR-0013（Library 状态机）；ADR-0012（per-Library 配置覆盖）

## Context

PRD §14.2 D7.1 要求 Library Dashboard（S2）显示 "Recent Activity" 时间线，混合所有 Library 的事件流。BACKEND_ROADMAP §2.6 把这条列为 P1 / S（2 天）的横切基础设施，并指出它是 ADR-0003「不接受 `library_ids: list`」纪律的**第一个例外案例**。

PRD §16.6 在本 ADR 起草前已被更新，加入了「L5 编排层例外条款」：

> **L5（编排层）例外**：允许组合**只读元视图**，例如：
> - 跨 Library 活动流（每条记录仍带 `library_id`，列表是 client-side / orchestration-side 聚合）
> - Library 列表与 Stats 总览
> - Eval Dashboard 的 Library 过滤器
> - ⌘K 命令面板的全局搜索
>
> 这些视图必须**只读**、**用户身份范围内**，不得从中触发跨 Library 的数据查询或写入。

这意味着 Activity Log 是这条例外条款的**首个落地**。它必须既满足业务需求（跨库聚合时间线），又不**实质性破坏** ADR-0003 的物理隔离与 protocol 纪律。

需要回答的问题：

1. 「只读元视图」的精确边界是什么？什么算 within-bounds，什么算违规？
2. 数据底层的 Protocol（`ActivityLogger`）应该怎么写，才能让上层"只读元视图"成为唯一的越界路径？
3. 跨库聚合查询的物理实现（多次单库查询拼合 vs 单 SQL `IN` 拼合）哪个更对？
4. 表分区、保留期、写入压力的工程取舍？

## Decisions

### 1. 例外条款的精确边界

**符合「只读元视图」的标准**（must satisfy ALL）：

1. **只读**：API endpoint 只能 `GET`；不允许跨库的 `POST/PUT/DELETE` 编排路径。
2. **每条记录原子归属于单一 library_id**：聚合是「在结果集层面把 N 个 library 的行 UNION 起来」，不是「构造一条跨库的复合记录」。
3. **下层 Protocol 仍是 per-library_id**：`ActivityLogger.record(library_id, event)`、`ActivityLogger.list(library_id, ...)`；跨库聚合是在 SQL 层（`WHERE library_id = ANY(?)`）或 orchestration 层（多次调用 + 内存合并）完成，**不下沉到 Protocol 签名**。
4. **结果集只用于展示**：API 响应不能被另一个写入路径作为"跨库批操作"的输入（例如不能 `GET /v1/activity` → `POST /v1/batch_action`）。
5. **用户身份范围内**：v1 是单租户，无身份过滤。M8+ 多用户化时，必须在 endpoint 层加 `WHERE owner_id = current_user`。

**不符合（必须拒绝）的例子**：

- ❌ `POST /v1/activity/cleanup?library_ids[]=a&library_ids[]=b`（写入路径，触发跨库副作用）
- ❌ `GET /v1/cross_library_qa?library_ids[]=a,b&question=...`（数据查询，跨库实际检索）
- ❌ `ActivityLogger.list_many(library_ids: list[str])`（Protocol 接受 list，破坏 ADR-0003 § 6 硬规矩）
- ❌ "聚合实体合并视图"（产生跨库的派生数据）

**Activity Log 落入符合的一边**，因为：每条 `ActivityEvent` 都带单值 `library_id`；聚合发生在 SQL `IN` 子句；端点 `GET /v1/activity` 是只读；结果只被前端 timeline 消费。

### 2. 表 schema 与按月分区

```sql
CREATE TABLE activity_log (
    id BIGSERIAL,
    library_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
PARTITION BY RANGE (created_at);

-- 每月一个分区；v1 阶段用 pg_partman 自动维护
SELECT partman.create_parent(
    p_parent_table => 'public.activity_log',
    p_control => 'created_at',
    p_type => 'range',
    p_interval => '1 month',
    p_premake => 3
);

CREATE INDEX activity_log_lib_created_idx
    ON activity_log (library_id, created_at DESC);

CREATE INDEX activity_log_lib_type_created_idx
    ON activity_log (library_id, type, created_at DESC);
```

设计要点：

- **分区键 = `created_at`**：时间分区，老分区可整体 drop；按 library_id 分区会让分区数膨胀（每个 Library × 每个月），失去意义。
- **(library_id, created_at DESC) 索引**：单库时间线查询的主要路径；DESC 与"从最新往老看"的 UI 行为对齐。
- **(library_id, type, created_at) 第二索引**：用于过滤特定事件类型（例如「这个库的 ingest_failed 历史」）。
- **`payload` 是 JSONB**：与 ADR-0012 同样的 schema 演进策略；不预先冻结 schema。
- **`actor`**：v1 填 `"system"` / `"api_key"` / `"cli"`；M8 多用户化时填 user_id。
- **`id BIGSERIAL`** 与 timestamp 配合：高并发写时 timestamp 可能撞同一微秒，bigserial 提供严格全序；前端做"加载更多"分页时用 `(created_at, id) < (?, ?)` keyset pagination。

### 3. 事件类型枚举（Closed Set，v1）

```python
# packages/orchestration/activity.py

class ActivityEventType(StrEnum):
    INGEST_COMPLETED = "ingest_completed"
    INGEST_FAILED = "ingest_failed"
    KG_EXTRACTED = "kg_extracted"
    COMMUNITY_REBUILT = "community_rebuilt"
    REVIEW_COMPLETED = "review_completed"
    REASON_COMPLETED = "reason_completed"
    HYPOTHESIZE_COMPLETED = "hypothesize_completed"
    LIBRARY_PURGED = "library_purged"
    LIBRARY_STATUS_CHANGED = "library_status_changed"     # ADR-0013
    LIBRARY_CONFIG_UPDATED = "library_config_updated"     # ADR-0012
```

加事件类型的策略：**在 ADR 中显式增**，不是开放枚举。每加一个类型都要回答："UI 怎么渲染它？payload 含什么？历史数据如何回填？"。前端有一张 `eventTypeRenderers.ts` 字典，与本枚举一一对应；新类型未添加渲染器时退化为通用渲染（icon=info, title-only）。

### 4. `ActivityEvent` 模型

```python
# packages/orchestration/activity.py

class ActivityEvent(BaseModel):
    """One activity log row. Always belongs to exactly ONE library_id."""
    id: int                              # BIGSERIAL
    library_id: str                      # 单值，绝不是 list
    type: ActivityEventType
    title: str                           # 短标题，UI 直接显示
    summary: str | None = None           # 可选 1-2 行摘要
    payload: dict = Field(default_factory=dict)
    actor: str = "system"
    created_at: datetime

    model_config = ConfigDict(frozen=True)  # 不可变；写入后只 read

class ActivityEventInput(BaseModel):
    """What callers pass to record(). id and created_at are server-assigned."""
    library_id: str
    type: ActivityEventType
    title: str
    summary: str | None = None
    payload: dict = Field(default_factory=dict)
    actor: str = "system"
```

注意 `library_id` 是 `str`，**不是** `list[str]`；从模型定义层就堵死了"一条事件跨多库"的语义。

### 5. `ActivityLogger` Protocol — 严守 ADR-0003 纪律

```python
# packages/orchestration/activity.py

class ActivityLogger(Protocol):
    """Per-Library activity logger.

    INVARIANT: This Protocol NEVER accepts library_ids: list[str].
    Cross-library aggregation is exclusively the L5 endpoint's responsibility,
    implemented via SQL `WHERE library_id = ANY(?)` directly against the
    underlying table — NOT through this Protocol.
    """

    async def record(self, event: ActivityEventInput) -> ActivityEvent:
        """Record one event. Returns the persisted event with id+created_at."""
        ...

    async def list(
        self,
        library_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        types: list[ActivityEventType] | None = None,
        limit: int = 50,
        cursor: tuple[datetime, int] | None = None,
    ) -> list[ActivityEvent]:
        """List events for ONE library. Per ADR-0003, no list-of-libraries.

        Cursor is (created_at, id) for keyset pagination.
        """
        ...
```

**禁止**的方法（任何 PR 中出现都直接拒）：

```python
# ❌ 绝不允许
async def record_many(self, events: list[ActivityEventInput]) -> ...:
    """Even if all events share library_id — still no, because the signature
    accepting a list invites future misuse."""

# ❌ 绝不允许
async def list_many(self, library_ids: list[str], ...) -> ...:
    """Cross-library aggregation belongs in L5, not in this Protocol."""

# ❌ 绝不允许
async def list_all(self, ...) -> ...:
    """Implies whole-system read; if needed, must be a separate
    AdminActivityReader Protocol explicitly tagged as L5."""
```

### 6. L5 endpoint 设计

```python
# apps/api/routes/activity.py

@router.get("/v1/activity", response_model=list[ActivityEvent])
async def list_activity(
    library_ids: list[str] = Query(..., max_items=20),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    types: list[ActivityEventType] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    principal: Principal = Depends(get_current_principal),
) -> list[ActivityEvent]:
    """Cross-Library activity feed.

    PRD §16.6 L5 exception: allowed because
    - read-only (GET);
    - each row is owned by single library_id;
    - aggregation is server-side SQL `library_id = ANY(?)`;
    - filtered by user identity (placeholder in v1; real ACL in M8+).
    """
    # v1 placeholder:权限校验（M8 真ACL）
    _verify_user_can_read_libraries(principal, library_ids)

    # 验证每个 library_id 都存在；拒绝任意一个不存在则整体 404
    for lib_id in library_ids:
        if not await library_store.exists(lib_id):
            raise LibraryNotFoundError(lib_id)

    decoded_cursor = _decode_cursor(cursor)
    rows = await activity_db.list_for_libraries(
        library_ids=library_ids,
        since=since,
        until=until,
        types=types,
        limit=limit,
        cursor=decoded_cursor,
    )
    return rows
```

`activity_db.list_for_libraries` 不属于 `ActivityLogger` Protocol；它是一个**显式 L5 only** 的 reader：

```python
# apps/api/_activity_reader.py  (注意路径在 apps/api，不是 packages/)

class ActivityCrossReader:
    """L5-only reader for the cross-library activity view.

    This class is INTENTIONALLY not a Protocol in packages/orchestration/.
    It exists only because PRD §16.6 grants L5 a read-only meta-view exception.
    Anything in packages/* that wants 'all libraries' must instead loop
    library-by-library through ActivityLogger.list().
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_for_libraries(
        self,
        *,
        library_ids: list[str],
        since: datetime | None,
        until: datetime | None,
        types: list[ActivityEventType] | None,
        limit: int,
        cursor: tuple[datetime, int] | None,
    ) -> list[ActivityEvent]:
        sql = """
            SELECT id, library_id, type, title, summary, payload, actor, created_at
            FROM activity_log
            WHERE library_id = ANY($1::text[])
              AND ($2::timestamptz IS NULL OR created_at >= $2)
              AND ($3::timestamptz IS NULL OR created_at <= $3)
              AND ($4::text[] IS NULL OR type = ANY($4))
              AND ($5::timestamptz IS NULL OR (created_at, id) < ($5, $6))
            ORDER BY created_at DESC, id DESC
            LIMIT $7
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, library_ids, since, until, types,
                                     cursor[0] if cursor else None,
                                     cursor[1] if cursor else None,
                                     limit)
        return [_row_to_event(r) for r in rows]
```

**为什么 reader 在 `apps/api/`，不在 `packages/`**：

- `packages/` 是被分层规则约束的领域代码；其中所有 Protocol 都遵守 ADR-0003。
- `apps/api/` 是 L5 编排层；`apps/api/_activity_reader.py` 是「写在 API 路由旁边的 SQL helper」，性质上接近视图查询，不是 domain protocol。
- 这条物理分离让`tach check` 仍然通过（packages 不引入跨库聚合方法），同时让 L5 例外有一个清晰的代码位置。
- 命名 `_activity_reader.py` 带下划线前缀，标识「私有 helper，不是公共契约」。

### 7. 写入时机：各 Worker Job 终态

各 worker job 在终态调用 `activity_logger.record`：

```python
# apps/worker/jobs/ingest_document.py
@arq.task(name="ingest_document")
async def ingest_document(ctx, library_id, file_sha256, ...):
    try:
        result = await _do_ingest(...)
        await ctx["activity_logger"].record(ActivityEventInput(
            library_id=library_id,
            type=ActivityEventType.INGEST_COMPLETED,
            title=f"Ingested {result.filename}",
            summary=f"{result.chunk_count} chunks, {result.duration_s:.1f}s",
            payload={
                "doc_id": result.doc_id,
                "chunk_count": result.chunk_count,
                "duration_s": result.duration_s,
                "file_sha256": file_sha256,
            },
        ))
        return result
    except Exception as e:
        await ctx["activity_logger"].record(ActivityEventInput(
            library_id=library_id,
            type=ActivityEventType.INGEST_FAILED,
            title=f"Ingestion failed",
            summary=str(e)[:200],
            payload={"file_sha256": file_sha256, "error": repr(e)},
        ))
        raise
```

写入路径与业务逻辑解耦：失败也 emit 事件；不影响业务返回值。

### 8. 写入压力评估与异步策略

**估算**：

- v1 单租户、5 用户、单 worker 进程；
- 主要事件源：ingest_completed（~ 100/天）、kg_extracted（~50/天）、community_rebuilt（~5/天）、review/reason/hypothesize_completed（< 50/天）、status_changed（< 100/天）；
- 合计 < 500 事件/天 ≈ 0.006 写/秒。

**结论**：v1 不需要 Outbox 模式、不需要批量写、不需要 Kafka。每条事件做**同步写**（与 worker job 的事务绑定，原子性更好）；若同步写失败，整个 job 标 failed 并重试。

**v1.1+ 触发条件**（任意一条触发就升级）：

- 写 QPS > 50（按当前结构估算需要 100× 用户量）；
- 跨进程 worker 拆分，需要"产生事件的进程 ≠ 写库的进程"；
- 用户希望 activity 即使 worker job 部分失败也保留（要求弱原子性）。

升级路径：在 `ActivityLogger` 适配器内部加一层 in-memory queue + 后台 flush worker；Protocol 签名不变。

### 9. 保留期与 Archive

**默认保留 90 天**。理由：

- Recent Activity UI 只展示最近 30 天；90 天给"研究项目周期"留缓冲；
- 超过 90 天的事件在 timeline 中价值 marginal，但占 storage；
- pg_partman 自动管理：`retention => 90 days`，老分区被 detach 后压缩归档（v1 直接 drop；archive 是 v1.1 的事）。

**Archive 选项（v1.1）**：detach 老分区到独立 schema `activity_archive`，按需手动 dump 到 S3 兼容存储。提供 CLI：

```bash
rkb activity archive --before 2026-02-01 --to s3://backups/activity/
```

### 10. 跨库 N+1 查询的避免

天真实现可能是：

```python
# ❌ 错的写法
events = []
for lib_id in library_ids:
    events.extend(await activity_logger.list(lib_id, limit=50))
events.sort(key=lambda e: e.created_at, reverse=True)
return events[:limit]
```

这会发出 N 个 SQL，每个都跑一遍 ORDER BY + LIMIT，总返回量 N×50；前端拿到的还得二次排序裁剪。

**正确实现**（§6 已写）：单 SQL `WHERE library_id = ANY(?)` ORDER BY + LIMIT。Postgres 在 `(library_id, created_at DESC)` 索引下能用 index merge 高效拼合。EXPLAIN 验证：v1 测试库 5 库 × 1 万行，总耗时 < 5 ms。

### 11. 用户身份越权（v1 单租户假设）

**v1 假设**：单租户、单 API key 持有者；Activity Log 没有 owner_id 列。`library_ids[]` 参数可访问任意库；这是**已知缺陷**，依赖前置 ADR-0007 的 Bearer auth + 单租户假设。

**M8 多租户改造**（计划路径）：

1. `libraries` 加 `owner_id` 列（M8 ACL ADR）；
2. `activity_log` 跟随，加 `owner_id`（denormalized；写入时从 library 拷贝）；
3. `ActivityCrossReader.list_for_libraries` 加 `WHERE owner_id = $current_user`；
4. 缺失 `owner_id` 的老数据视为 `system` 拥有，仅 admin 可见。

不在 v1 处理；保持本 ADR 关注 §16.6 例外条款本身。

## Consequences

### Positive

- **§16.6 例外条款有了"参考实现"**：未来 ⌘K 全局搜索（ADR-0023）和跨库 KPI（§3.2 Gap 5）按本 ADR 的"L5 reader 模式"复制即可。
- **Recent Activity UI 真实可用**：S2 时间线由真实事件驱动，不是 mock。
- **审计能力**：`library_purged` / `library_config_updated` / `library_status_changed` 全部留痕，运维可回溯。
- **写路径简单**：所有 worker job 的"我做完了"信号统一走一个 Protocol；Reviewing PR 时容易检查"忘记 emit activity 没"。

### Negative

- **L5 例外会被滥用**：开了一个口子，未来 PR 可能引用本 ADR 来"绕过 ADR-0003"。缓解：本 ADR §1 明确列举允许/禁止的例子；Code Review checklist 增条目 "新的 L5 跨库 reader 是否符合 ADR-0014 §1 的 5 条标准"。
- **JSONB payload 难以全文搜索**：v1 不需要；v1.1 若用户想"按 doc_id 找所有 activity"，需要 expression index。
- **没有事件 schema 校验**：每个事件类型的 payload 字段是隐式约定。缓解：在 `packages/orchestration/activity_payloads.py` 给每个 type 写一个 TypedDict 文档，PR review 检查。

### Risks

| ID | 风险 | 缓解 |
|---|---|---|
| A01 | 漏 emit 事件（worker job crash 在 record 之前） | 业务逻辑放 record 之后；fail 路径包在 try/except 内；定期对比 task_queue 完成数 vs activity 行数 |
| A02 | 重复 emit（worker retry） | activity_log 不做去重（每次重试一条 ingest_failed 是正常的）；UI 要忍受相邻重复 |
| A03 | 跨库查询的安全越权（v1 单租户掩盖） | 已在 §11 列为已知缺陷；M8 改造路径明确 |
| A04 | pg_partman 没装的环境分区表手动维护痛苦 | runbook 提供手动 SQL；v1 docker-compose 已包含 pg_partman extension |
| A05 | 90 天保留期对长项目用户不够 | v1.1 archive；用户可手动 dump 整表 |
| A06 | 单 SQL 在大表（百万行）变慢 | 月分区使热数据集小；keyset pagination 避免 OFFSET 性能塌方 |

## Alternatives Considered

| 选项 | 描述 | 拒绝原因 |
|---|---|---|
| **Postgres 逻辑复制 / CDC + 派生 activity 视图** | 用 Debezium/wal2json 监听 documents/communities/tasks 表变更，自动生成 activity | 复杂度爆炸；CDC pipeline 需要额外组件；事件粒度被 schema 决定，不灵活 |
| **事件表 + 物化视图** | activity_raw 写原始事件，定期 REFRESH MATERIALIZED VIEW 出聚合视图 | 物化视图刷新有延迟；UI 体验差；增量刷新支持不完整 |
| **每个 Library 一张表 `activity_<library_id>`** | 物理隔离极致 | 跨库 UNION 在 N 库时性能塌；建表/删表运维负担；与 ADR-0003 的"列分区"原则冲突 |
| **直接复用 Langfuse trace 流** | Langfuse 已有 task trace | Trace 粒度过细（一个任务里 N 个 LLM 调用都是 trace），不是用户视角的 activity；且 Langfuse 数据不在 Postgres，跨库查询不便 |
| **Outbox + Kafka** | 写库时同时写 outbox 表，consumer 推送到 Kafka，Activity Log 是 Kafka topic 的一个 subscriber | v1 写量太低；额外组件不值；保留为 v2 演进路径 |
| **NoSQL（Mongo / DynamoDB）存 activity** | schema-free + 快写 | 跨 storage 引入；查询 SQL `IN` 拼合就够用；Postgres JSONB 已是 schema-free |
| **把 activity 字段直接挂在 task 表** | `tasks` 已有 status/timestamp，加几个 title/summary 列 | 限制为"任务相关 activity"；status_changed/config_updated 没有对应任务；语义混乱 |
| **`ActivityLogger.list_many(library_ids)`** | Protocol 接受 list 让代码更短 | 直接破坏 ADR-0003；本 ADR 整个 §5 反对的就是这个；任何短代码收益不抵这个口子 |

## Open Questions

1. **是否给 activity 加分类标签（severity / category）便于 UI 过滤？**
   - v1 不加；UI 用 `type` 单维度过滤足够。v1.1 若需要"只看错误"，可加 `severity` 列（与 Notification ADR-0011 对齐）。
2. **是否允许 actor 字段含 user-provided 值（risk: log injection）？**
   - v1 actor 由后端写死，不接受请求体传入；前端无法注入。
3. **`payload` 的最大体积如何限制？**
   - 软限制 8 KB；超过则截断 + 记 warning log。Pydantic validator 在 `record()` 入口做。
4. **跨进程 worker 后，Activity Log 是否要按 worker_id 标签？**
   - v2 再考虑；v1 单 worker 不需要。
5. **何时把 §5 的 list/list_many/list_all 三条禁令也写进 CODING_STANDARDS？**
   - 本 ADR merged 当日；CODING_STANDARDS §6.5 增一条引用本 ADR §5。
6. **library_id 不存在的情况**：record 时若 library_id 不存在（比如已被 purge），`activity_log` 表的 FK 是否设？
   - v1 **不设 FK**：activity 可以"晚于" library 存在（ingest 完成时 library 仍在；purge 时 library 删了，但 `library_purged` 事件本身需要保留）。等 purge 后保留期内的 activity 是孤儿，但具有审计价值。

## Relationship to Other ADRs

- **ADR-0003**（Library as Data Partition）— 本 ADR 是其 §6.5 「禁止 `library_ids: list`」的**第一个明示例外**，并通过 §1 明确边界、§5 把 Protocol 严格限制在 per-library，将"例外"局部化在 L5 endpoint。
- **ADR-0007**（M7 Error Envelope）— Activity 端点错误也走统一信封；library_id 不存在用 `LibraryNotFoundError`。
- **ADR-0011**（通知中心）— 与 Activity Log 是**两条独立通道**：
  - Notification = 推（瞬时；用户可见的红点）；
  - Activity = 拉（持久；时间线回溯）。
  - 同一事件可同时写两边（例如 ingest_completed → 一条 Notification + 一条 ActivityEvent）。
- **ADR-0012**（per-Library 配置覆盖）— `library_config_updated` 事件类型由 ADR-0012 写入路径触发。
- **ADR-0013**（Library 状态机）— `library_status_changed` 事件由巡检 job 触发；Activity Log 是 status 历史的唯一可追溯位置。
- **ADR-0022**（Library Purge）— Purge 操作 emit `library_purged` 事件并保留 90 天；purge 不级联删除该 library 的历史 activity 行（保审计完整）。
- **ADR-0023**（⌘K 跨资源搜索）— 与本 ADR 共同遵循"L5 read-only meta-view"模式；ADR-0023 起草时引用本 ADR §1 的 5 条标准。

## References

- BACKEND_ROADMAP.md §2.6（Activity Log）
- BACKEND_ROADMAP.md §6 — P1 列表
- PRD §14.2 D7.1（Library Dashboard 含 Recent Activity）
- PRD §16.6（Library 维度纪律 + L5 例外条款）
- CODING_STANDARDS §6.5（Library 维度硬规矩）
- 实现位置：
  - `packages/orchestration/activity.py`（新）— `ActivityEvent`、`ActivityEventInput`、`ActivityEventType`、`ActivityLogger` Protocol
  - `packages/storage/postgres/activity_logger.py`（新）— Postgres 适配器，per-library 写
  - `apps/api/routes/activity.py`（新）— `GET /v1/activity` L5 endpoint
  - `apps/api/_activity_reader.py`（新）— L5-only `ActivityCrossReader`
  - `apps/worker/jobs/*.py` — 终态调 `activity_logger.record`
  - `migrations/00X_activity_log.sql`（新）— 表 + 分区 + 索引

---

**Decision owners**: Architect
**Review cycle**: M7 α 测试结束后回看 §1 边界规则是否被实际遵守；M8 多租户化前重写 §11。
