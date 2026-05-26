# ADR-0013: Library Status Machine

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M7 D7.1（Library Dashboard 状态徽章）；BACKEND_ROADMAP §2.5
**Related**: ADR-0003（Library as Data Partition）；ADR-0011（Notification Center）；ADR-0014（Activity Log）

## Context

PRD §16.7 已经定义了 Library 的三态枚举 `Healthy / Indexing / Stale community`，UI 上的 Library Dashboard（S2）需要据此渲染状态徽章。但当前实现没有对应的数据源：

- `libraries` 表无 `status` 列；
- 没有任何后台 job 在维护这个状态；
- 前端 `LibraryDashboard.vue` 临时硬编码所有库为 `Healthy`，是个明显的功能缺口。

需要解决的问题：

1. **状态来源**：状态应该是「事实推断」（每次读时计算）还是「持久化字段」（写入时维护）？
2. **判定阈值**：`Stale community` 的「7 天 + 50 篇新文档」从哪来？是否合理？是否要 per-Library 可配？
3. **巡检节奏**：状态会自动恢复（例如 community rebuild 跑完后 Stale → Healthy），需要周期 job 推进；频率多高？
4. **并发安全**：同时跑 ingest + KG extract + community rebuild 时，状态怎么写不打架？
5. **失败兜底**：若 community rebuild 任务挂了，库是不是会永远停在 `Indexing`？

BACKEND_ROADMAP §2.5 把这条列为 P1 / S（2–3 天），并明确说"状态变化触发 Notification"，需要与 ADR-0011 联动。

## Decisions

### 1. 状态持久化为 Postgres 列；后台 job 周期推进

`libraries` 表新增两列：

```sql
ALTER TABLE libraries
    ADD COLUMN status TEXT NOT NULL DEFAULT 'healthy'
        CHECK (status IN ('healthy', 'indexing', 'stale_community')),
    ADD COLUMN status_updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX libraries_status_idx ON libraries(status)
    WHERE status != 'healthy';  -- partial index: 只索引非健康态
```

- **不做实时推断**：每次 `GET /v1/libraries` 都跑一遍判定逻辑会让列表查询变慢，且会造成同一时刻不同 reader 看到不同状态。持久化为列 + 周期 job 维护 + Activity Log 留痕，是 v1 最简方案。
- **不引入独立状态表**：状态属于 Library 的一阶属性，不是事件流；放回 `libraries` 表与 ADR-0003 的 mental model 一致。
- **partial index**：绝大多数 Library 处于 `healthy`；查询「找出当前不健康的库」只命中少数行，partial index 既省空间又快。

### 2. 三态枚举与状态转移图

```python
# packages/core/models.py

class LibraryStatus(StrEnum):
    HEALTHY = "healthy"
    INDEXING = "indexing"
    STALE_COMMUNITY = "stale_community"

class Library(BaseModel):
    library_id: str
    name: str
    description: str | None = None
    primary_language: Literal["en", "zh", "mixed"] = "en"
    status: LibraryStatus = LibraryStatus.HEALTHY
    status_updated_at: datetime
    created_at: datetime
```

**允许的状态转移**（以下任意一对都允许；其余的视为非法）：

```
            ┌──────────────┐
            │              │
            ▼              │
       ┌────────┐          │
   ┌──▶│Indexing│──────────┼─────┐
   │   └────────┘          │     │
   │       ▲               │     ▼
   │       │           ┌───┴────────────┐
   │       └───────────│ Stale community│
   │                   └────────────────┘
   │                            ▲
   │                            │
   │                            │
┌──┴────┐                       │
│Healthy│───────────────────────┘
└───────┘  (≥ 7d & +50 docs without rebuild)
   ▲
   │  (rebuild done | new ingest empty | manual reset)
```

明确**禁止**的转移：

- 不存在 `Healthy → Stale community → Healthy` 的"自愈"——必须经过一次 `Indexing`（即至少跑一次 community rebuild）。
- 不存在 `任意 → Indexing` 的强制写入由 API 路径直接发起；只能由 worker 在拿到任务时写入。

### 3. 判定阈值（v1 硬编码，不可配）

```python
# packages/core/library_admin.py

STALE_AGE_THRESHOLD = timedelta(days=7)
STALE_DOC_COUNT_THRESHOLD = 50
STATUS_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
```

**判定逻辑**：

```python
async def evaluate_status(library_id: str) -> LibraryStatus:
    # 1. 是否有正在跑的索引类任务？
    active_tasks = await task_queue.list_active(library_id)
    if any(t.task_type in {"ingest", "kg_extract", "community_rebuild"}
           for t in active_tasks):
        return LibraryStatus.INDEXING

    # 2. community 是否陈旧？
    last_rebuild = await community_store.get_last_rebuild_time(library_id)
    if last_rebuild is None:
        # 一篇文档都没建过 community 摘要——不算 stale，仍是 healthy
        return LibraryStatus.HEALTHY

    age = datetime.now(UTC) - last_rebuild
    if age < STALE_AGE_THRESHOLD:
        return LibraryStatus.HEALTHY

    new_docs = await doc_store.count_added_since(library_id, last_rebuild)
    if new_docs >= STALE_DOC_COUNT_THRESHOLD:
        return LibraryStatus.STALE_COMMUNITY

    return LibraryStatus.HEALTHY
```

注意几个细节：

- **`last_rebuild is None`**（从未跑过 community）的情况返回 `HEALTHY`，不返回 `STALE_COMMUNITY`——空库不应该一上来就告警。
- **新增文档计数用日历时间戳**（`> last_rebuild`）而非滑动窗口；理由见 §6 Open Questions。
- **`STALE_DOC_COUNT_THRESHOLD` 用「自上次 rebuild 起」的累计数**，不是「最近 7 天」的滑动数。前者更贴合 community rebuild 是「批量重新分群」的语义。

### 4. 巡检 job

```python
# apps/worker/jobs/library_status_check.py

@arq.task(name="library_status_check")
async def library_status_check(ctx: Context) -> None:
    """Periodic job. Cron: every 5 minutes."""
    libraries = await ctx["library_store"].list_all()
    for lib in libraries:
        await _check_one(ctx, lib)

async def _check_one(ctx: Context, lib: Library) -> None:
    new_status = await evaluate_status(lib.library_id)
    if new_status == lib.status:
        return  # no-op

    # 用 advisory lock 防止两个巡检 worker 抢
    async with ctx["pg"].advisory_xact_lock(_lock_key(lib.library_id)):
        # double-check after acquiring lock
        cur = await ctx["library_store"].get(lib.library_id)
        if cur.status == new_status:
            return
        await ctx["library_store"].update_status(lib.library_id, new_status)
        await ctx["activity_logger"].record(
            library_id=lib.library_id,
            type="library_status_changed",
            title=f"Status: {cur.status.value} → {new_status.value}",
            payload={"from": cur.status.value, "to": new_status.value},
        )
        await ctx["notifier"].send(
            library_id=lib.library_id,
            type="library_status_changed",
            severity=_severity_for(new_status),
            title=f"{lib.name} is now {new_status.value}",
        )

def _lock_key(library_id: str) -> int:
    return hash(("library_status", library_id)) & 0x7fffffff
```

**频率选择**：每 5 分钟。理由：

- 太密（< 1 min）：浪费 Postgres 连接，且对用户感知无益（人不会每秒都看 Dashboard）；
- 太疏（> 15 min）：用户可能等很久才看到 status 翻转；
- 5 min 与 PRD §14.4 D7.5 中"任务完成 30 秒内顶栏 Notify"的 SLA 不冲突，因为状态翻转的 Notification 是次要通道（首要是 task_completed Notification）。

**幂等保证**：

- Job 每次跑一遍全量库表，不依赖外部触发；漏跑一轮不会累积 backlog。
- `update_status` 用 advisory lock + double-check pattern 保证并发巡检 worker 不写花。
- `evaluate_status` 是纯读取，无副作用；可以反复调用。

### 5. 与异步任务的并发安全

巡检 job 用 `task_queue.list_active(library_id)` 拿"当前在跑的任务"。但这里有个**并发窗口**：

```
T0   巡检 job 开始
T0+ε  task_queue.list_active() 返回 []  → 判 healthy
T1   巡检 job 还在跑
T2   用户提交 ingest 任务，worker 把它标记为 running
T3   巡检 job UPDATE libraries SET status='healthy'  ← 错了！

```

**缓解策略 1（v1 采纳）**：worker 在 `ingest_document` / `extract_kg` / `rebuild_community` 这三类 job 的入口处**主动写** `status = INDEXING`，不等巡检 job：

```python
# apps/worker/jobs/ingest_document.py
@arq.task(name="ingest_document")
async def ingest_document(ctx, library_id: str, ...) -> ...:
    await ctx["library_store"].update_status_if_not(
        library_id, current=LibraryStatus.INDEXING,
    )
    try:
        ...
    finally:
        # 任务结束不清状态——交给下一轮巡检 job 复算
        pass
```

`update_status_if_not(library_id, current)` 的语义：「如果当前不是 current，则置为 current」。这样：

- 多个 ingest 任务并发跑，第一个写 `Indexing`，其余 no-op；
- Stale community 状态被 ingest 任务立即覆盖为 Indexing（业务上合理：开始 ingest 就不算 stale 了）；
- 任务结束时**不写回 healthy**，让巡检 job 在下一轮统一判断（避免「ingest 完了但 community 还没跑」却被错误标 healthy）。

**缓解策略 2（兜底）**：巡检 job 在 advisory lock 内做 double-check（§4 已写）。即使巡检 job 看到 `[]` 但已被新任务抢先写 `Indexing`，double-check 时会读到最新状态，no-op 退出。

### 6. 状态变化的下游联动

| 状态变更 | Notification | Activity Log | UI 表现 |
|---|---|---|---|
| `Healthy → Indexing` | severity=`info`，标题 `<lib> is indexing` | `library_status_changed` 事件 | 卡片徽章变蓝；右上角 spinner |
| `Indexing → Healthy` | severity=`info`，标题 `<lib> is now healthy` | 同上 | 卡片徽章变绿 |
| `Indexing → Stale community` | severity=`warning`，标题 `<lib> needs community rebuild` | 同上 | 卡片徽章变琥珀；顶栏红点 |
| `Healthy → Stale community` | severity=`warning`，同上 | 同上 | 同上 |
| `Stale community → Indexing`（用户点 Rebuild） | severity=`info` | 同上 | 同 Healthy → Indexing |
| `Stale community → Healthy` | **不发**（间接通过下一次 Indexing → Healthy 触达） | 仍发 | — |

**为什么 `Stale → Healthy` 不发**：因为这要求经过 Indexing；Indexing → Healthy 已经发了，再发一次 Stale → Healthy 就是重复噪声。

### 7. 失败兜底 — 防止"永远 Indexing"

若 community rebuild 任务挂了（worker crash、Redis 丢消息、被 cancel 但状态没复位），库会停在 Indexing。两道护栏：

1. **巡检 job 在 `evaluate_status` 中用 `task_queue.list_active`**，而不是无脑沿用上一次状态；list_active 只返回 `queued | running` 的任务。如果任务因 crash 进入 `failed`，不会被 list_active 返回，下一轮巡检自然回到 Healthy/Stale。
2. **超时阈值**：若 status 是 Indexing 且 `status_updated_at > 24h`（远长于任何合法任务），巡检 job 强制 emit 一条 `severity=warning, type=alert_triggered` 通知给运维，提示「Library X 在 Indexing 状态超 24h，疑似任务丢失」。不自动复位状态——让运维决定（可能是人工跑 `library status reset`）。

### 8. CLI 与 admin endpoint

提供一个**手动复位**的下逃门：

```bash
rkb library status <library_id> --set healthy --reason "manual recovery after worker crash"
```

后端走 `POST /v1/admin/libraries/{lib}/status`（API key 鉴权），写一条 Activity Log 记录人工复位的事实。

## Consequences

### Positive

- **UI 真实可信**：Library Dashboard 的徽章不再是硬编码 mock，与后端实际任务状态对偶。
- **告警友好**：用户灌入 60 篇新文档后 7 天没跑 community rebuild，Notification 主动提醒，避免"用了一个月才发现 community 摘要老旧"。
- **复杂度可控**：单列 + 单巡检 job + 五种状态转移；新人 30 分钟能读懂。

### Negative

- **延迟最长 5 分钟**：状态变化与 UI 反映之间有最长 5 分钟的窗口；通过任务边界主动写 Indexing 缓解了「任务开始」的延迟，但「任务完成 → 重新判断」仍是 5 min。
- **没有 per-Library 阈值**：用户灌的论文体量差异巨大（10 篇 vs 10000 篇），统一的"50 篇 / 7 天"对小库太敏感、对大库太迟钝。v1 接受这个代价；v1.1 做 per-Library 可配（与 ADR-0012 联动）。
- **24h 超时只发警告不自愈**：要求运维介入；权衡：自动复位风险更高（可能掩盖真实 bug），告警 + 手动复位更安全。

### Risks

| ID | 风险 | 缓解 |
|---|---|---|
| S01 | 巡检 job 自身挂了，所有状态卡住 | Arq 自带 health check + worker 监控；ADR-0009 中的 worker 心跳机制 |
| S02 | Postgres advisory lock 在多实例 worker 部署下不够（v1 单进程 worker，不存在；v2 拆 worker 时需检查） | v1 文档注明假设；v2 切真分布式锁（Redlock 或 Postgres pg_locks） |
| S03 | `count_added_since` 在百万级文档库上变慢 | `documents` 表 `(library_id, created_at)` 复合索引；预估 v1 单库 < 5000 篇，不是问题 |
| S04 | Stale community 阈值 7 天对快速迭代用户太短 | v1 接受；ADR-0012 的 `library_config.overrides` 已为 v1.1 per-库配预留位 |
| S05 | 用户在 Indexing 期间删 Library | ADR-0022（Library Purge）保证 purge 会先 cancel 所有任务；状态机看到任务消失，下一轮自然不再判 Indexing |

## Alternatives Considered

| 选项 | 描述 | 拒绝原因 |
|---|---|---|
| **每次 GET 实时计算状态** | `GET /v1/libraries` 内联跑 `evaluate_status` | Library 列表变慢；不同 reader 看到不同瞬时状态；无法 emit 状态变化 Notification |
| **用 Postgres advisory lock 代替 status 列** | "持有锁 = Indexing"，无显式状态字段 | UI 还是要从 pg_locks 反查；锁 semantics 不便于「Stale community」这种非阻塞态；可读性差 |
| **用 Redis SET 维护 active_libraries** | `SADD indexing_libs <id>` / `SREM indexing_libs <id>` | Redis 重启状态丢；与持久化的 `libraries` 表不一致；多 worker 部署需要严格清理 |
| **per-Library 可配阈值**（v1 实施） | 把 7d/50 写进 `library_config` | 增加 API 表面与测试矩阵；v1 用户量小，硬编码可接受；v1.1 再做 |
| **用 EventBus 推驱替代周期巡检** | 任务终态 emit event，listener 写 status | 仍需要兜底巡检（任务漏发 event 怎么办？）；引入两条路径；v1 单巡检路径足够 |
| **状态枚举多到 5 态**（如增加 `partially_indexed` / `embedder_changed`） | 表达力更强 | 三态已能驱动 PRD §16.7 表格；多了 UI 难以解释 |

## Open Questions

1. **判定时间窗：日历日 vs 滑动窗口？**
   - v1 选**自上次 rebuild 起的累计数**——`COUNT(*) WHERE created_at > last_rebuild`。理由：community rebuild 本身就是"批"语义；按"距上次 rebuild"度量与业务对齐。
   - 滑动窗口（最近 7 天 N 篇）的好处是对用户行为更敏感，但若用户连续 30 天每天 5 篇但从不 rebuild，滑动窗口永远不触发；这是误报 false negative。
2. **24h 超时是否应自愈？**
   - v1 不自愈，只 alert。M8 多用户后再考虑。
3. **`Indexing` 是否可以与 `Stale community` 共存？**（用户在已 stale 的库上启动了 ingest）
   - v1 选 `Indexing` 优先级高于 `Stale community`：只要有任务在跑，就显示 Indexing；rebuild 后通过下一轮巡检进入正确状态。理由：UI 上"正在做事"比"东西旧了"更重要——用户已经在动手了，再警告 stale 是噪声。
4. **per-Library 状态机内核是否要在 `LibraryStatus` 外保留一个 `StatusReason` 字符串字段？**
   - v1 不加；`status_updated_at` + Activity Log 已足够追溯原因。
5. **空 Library（0 文档）是 Healthy？**
   - 是。空库无任务、无 community → 落 Healthy 默认值。这与 PRD §16.7 一致（空集合默认健康）。

## Relationship to Other ADRs

- **ADR-0003**（Library as Data Partition）— `status` 字段作为 Library 一阶属性合并入 `libraries` 表，符合「数据维度而非分层」。
- **ADR-0009**（异步任务队列）— `task_queue.list_active(library_id)` 是状态判定的核心数据源；状态机依赖任务队列实现的正确性。
- **ADR-0011**（通知中心）— 状态变化必走 Notification 通道；severity 映射在 §6 表格。
- **ADR-0012**（per-Library 配置覆盖）— v1 阈值硬编码，v1.1 起支持 per-Library override；override 字段进 `library_config.overrides`。
- **ADR-0014**（Activity Log）— 每次状态变化写一条 `library_status_changed` 事件；Dashboard 时间线据此渲染。
- **ADR-0022**（Library Purge）— Purge 时 cancel 所有任务并删除 status 行（CASCADE）。

## References

- BACKEND_ROADMAP.md §2.5（Library 状态机）
- BACKEND_ROADMAP.md §6 — P1 列表
- PRD §16.7（Library 状态枚举）
- PRD §14.2 D7.1（Library Dashboard）
- 实现位置：
  - `packages/core/models.py` — `LibraryStatus` 枚举；`Library.status` 字段
  - `packages/core/library_admin.py` — `evaluate_status`；阈值常量
  - `apps/worker/jobs/library_status_check.py`（新）— 巡检 job
  - `apps/worker/jobs/ingest_document.py`、`extract_kg.py`、`rebuild_community.py` — 入口处主动写 Indexing
  - `migrations/00X_libraries_status.sql`（新）

---

**Decision owners**: Architect
**Review cycle**: M7 α 测试结束后回看阈值（7d/50 是否需要调整）；引入第二个 worker 实例前回看并发安全策略。
