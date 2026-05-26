# ADR-0012: per-Library Configuration Overrides

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M7 D7.6（per-Library 配置覆盖）；BACKEND_ROADMAP §2.4
**Related**: ADR-0003（Library as Data Partition）；ADR-0013（Library 状态机）；ADR-0015（Daily Cost Cap）

## Context

PRD §14.2 中 D7.6 要求："per-Library 配置覆盖 — LLM 路由 / Embedder / 检索预算 / 每日成本上限可在单 Library 内独立配置"。BACKEND_ROADMAP §2.4 把这条列为 P1，并指明它是 ADR-0015（Daily Cost Cap）和 ADR-0013（状态机）的前置依赖。

现状：

- `packages/core/settings.py` 提供唯一的全局 `Settings` 单例（pydantic-settings + 环境变量）。所有 LLM Gateway / Embedder Service / Retrieval Coordinator 都直接读这一个对象。
- 用户在前端建多个 Library 后，没有任何路径让某一个 Library 独立切换 Embedder（例如把中文库切到 `bge-m3`）、独立设置 LLM 主路由（例如把贵的库切到 `claude-haiku-4-5` 兜底）、或者独立调高检索预算。
- 没有 per-Library 成本上限的承载位置（这是 ADR-0015 的承载基础）。

需要解决的核心矛盾是：

1. **覆盖语义** — 「未设置」应该意味着「继承全局默认」，而不是「等于 null/空字符串」。覆盖必须能精确表达「这个 Library 显式选择了 X」与「这个 Library 没意见，跟全局走」的区别。
2. **schema 演进** — Embedder spec、LLM router、retrieval budget 这三类结构在 v1 周期内会反复增删字段。若每次加字段都要写 alembic migration，迭代摩擦过高。
3. **写入时机** — 切 Embedder 后旧索引（Qdrant collection 已经存了 4096 维向量）和新 Embedder（假设维度不同）不兼容。是强制 reindex，还是 UI 层 warning + 软兼容？
4. **下游耦合** — LLM Gateway / Embedder Service / Retrieval Budget 在每个请求边界都需要拿到「当前 Library 的有效配置」，这条调用必须便宜（< 1 ms）且失败时有合理降级。

## Decisions

### 1. 单表 + JSONB 列 — 不分表、不平铺、不版本化

新表 `library_config`，每行对应一个 Library，结构精简：

```sql
CREATE TABLE library_config (
    library_id TEXT PRIMARY KEY
        REFERENCES libraries(library_id) ON DELETE CASCADE,
    overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX library_config_overrides_gin
    ON library_config USING GIN (overrides jsonb_path_ops);
```

- **PRIMARY KEY 是 library_id**，删 Library 级联删配置（与 ADR-0003 物理隔离原则对偶）。
- **`overrides` 是 JSONB**，schema 完全在 Pydantic 端演进；DB 端只认「可序列化对象」。
- **GIN index** 仅服务于 v1.1 可能出现的「找出所有用 bge-m3 的 Library」类管理性查询，v1 不依赖该 index 的功能。
- **没有 `version` 列**，没有历史表，没有 audit trail 详记。`updated_at + updated_by` 是 v1 的全部审计；详细变更记录通过 ADR-0014 Activity Log 落 `library_config_updated` 事件类型来满足。

### 2. `LibraryConfig` 模型 — 三段式 override

```python
# packages/core/models.py

class LLMRouterSpec(BaseModel):
    primary: str            # e.g. "claude-haiku-4-5"
    fallback: list[str]     # ordered fallback chain
    prefer_local: bool = False

class EmbedderSpec(BaseModel):
    name: str               # "bge-m3" / "openai-3-large" / "qwen3-embedding"
    dim: int                # 必填；用于切 Embedder 时的维度兼容判断

class RetrievalBudget(BaseModel):
    max_chunks: int = 30
    max_hops: int = 2
    max_rerank_candidates: int = 50
    timeout_s: float = 30.0

class LibraryConfig(BaseModel):
    """Frozen view of a Library's effective configuration.
    None on any field means 'inherit from global default'."""
    library_id: str
    llm_router_override: LLMRouterSpec | None = None
    embedder_override: EmbedderSpec | None = None
    retrieval_budget_override: RetrievalBudget | None = None
    daily_cost_cap_usd: Decimal | None = None
    schema_yaml_path: str | None = None
    updated_at: datetime
    updated_by: str = "system"

class LibraryConfigPatch(BaseModel):
    """Partial update payload. Field not in payload = unchanged.
    Field set to explicit `None` = clear override (revert to global)."""
    llm_router_override: LLMRouterSpec | None = ...
    embedder_override: EmbedderSpec | None = ...
    retrieval_budget_override: RetrievalBudget | None = ...
    daily_cost_cap_usd: Decimal | None = ...
    schema_yaml_path: str | None = ...

    model_config = ConfigDict(extra="forbid")
```

`LibraryConfigPatch` 与 `LibraryConfig` 的 None 语义有微妙区别：

- 在 `LibraryConfig` 中，`None` = 「该字段未覆盖，使用全局默认」。
- 在 `LibraryConfigPatch` 中：
  - 字段不在 payload 里（pydantic `model_fields_set` 不含它） = 不动
  - 字段显式 `None` = 清除 override，回到全局默认
  - 字段有具体值 = 设置/更新 override

这与 PATCH/MERGE 的传统语义贴齐；前端可以发 `{"embedder_override": null}` 来清除一个之前设置的 Embedder。

### 3. Protocol 契约：`LibraryConfigStore`

```python
# packages/core/library_admin.py

class LibraryConfigStore(Protocol):
    async def get(self, library_id: str) -> LibraryConfig:
        """Return the Library's effective config.

        On a missing row, returns a LibraryConfig with all override
        fields = None (i.e. 'fully inherits global'). Never raises
        LibraryNotFoundError for missing config — only for missing Library.
        """
        ...

    async def update(
        self,
        library_id: str,
        patch: LibraryConfigPatch,
        *,
        updated_by: str = "system",
    ) -> LibraryConfig:
        """Apply a patch atomically. Returns the new full config."""
        ...

    async def reset(self, library_id: str) -> LibraryConfig:
        """Clear all overrides; equivalent to update with everything = None."""
        ...
```

注意契约的 4 条硬规矩（继承 ADR-0003）：

- 首参 `library_id`，无 `library_ids: list` 重载；
- 无返回 `dict[library_id, LibraryConfig]` 的批量方法（如果 L5 真的需要一次拉一堆，那是 SQL `WHERE library_id = ANY(?)` 的事，不下沉到 Protocol）；
- 不暴露 raw `overrides: dict` —— Pydantic 模型是契约的一部分；
- 实现可以是 Postgres、可以是 in-memory、可以是 sqlite，调用方一概不关心。

### 4. Override 解析：自下而上的三层合并

`LibraryConfig` 本身只记录 override；最终生效的「effective config」由调用方在每个请求边界做合并。我们提供一个 helper：

```python
# packages/core/library_admin.py

async def resolve_effective(
    library_id: str,
    *,
    config_store: LibraryConfigStore,
    settings: Settings,
) -> EffectiveLibraryConfig:
    """Merge order (lowest priority first):

    1. System hard-coded defaults (in `models.py` field defaults)
    2. Global settings (`Settings.llm_router_default`, etc.)
    3. Library override (this row's non-None fields)

    Returns a frozen EffectiveLibraryConfig — every field is non-None.
    """
    cfg = await config_store.get(library_id)
    return EffectiveLibraryConfig(
        library_id=library_id,
        llm_router=cfg.llm_router_override or settings.llm_router_default,
        embedder=cfg.embedder_override or settings.embedder_default,
        retrieval_budget=cfg.retrieval_budget_override or settings.retrieval_budget_default,
        daily_cost_cap_usd=cfg.daily_cost_cap_usd,  # None 表示无上限
        schema_yaml_path=cfg.schema_yaml_path or settings.schema_yaml_path_default,
    )
```

`EffectiveLibraryConfig` 是一个**所有字段都非 None** 的派生模型。它只在请求路径上短暂存在；它不入库。

### 5. 下游调用点

LLM Gateway 在路由前先取 effective config：

```python
# packages/llm/gateway.py
async def complete(library_id: str, prompt: str, ...):
    eff = await resolve_effective(library_id, config_store=..., settings=...)
    # daily cap check (ADR-0015) 在这里发生
    router = eff.llm_router
    return await self._route_and_complete(router, prompt, ...)
```

Embedder Service 同理：

```python
# packages/embedding/service.py
async def embed(library_id: str, texts: list[str]) -> list[list[float]]:
    eff = await resolve_effective(library_id, config_store=..., settings=...)
    embedder = self._embedders[eff.embedder.name]
    return await embedder.embed(texts)
```

Retrieval Budget 在 orchestration 层读：

```python
# packages/orchestration/budget.py
async def get_budget(library_id: str) -> RetrievalBudget:
    eff = await resolve_effective(library_id, ...)
    return eff.retrieval_budget
```

每个请求边界都重新解析。**不缓存 effective config**——简单、避免缓存失效问题；解析本身只做一次 JSONB 行读取，p99 < 2 ms。如果未来 profiling 显示这是热点，再加 in-memory TTL 缓存（建议 60 s）。

### 6. 切换 Embedder 的兼容性 — v1 不强制 reindex

这是本 ADR 最有争议的点。三种选择：

| 选项 | 行为 | v1 选择 |
|---|---|---|
| A. 切 Embedder 立即触发 reindex 任务 | 自动正确，但调用昂贵；用户可能误操作 | ❌ |
| B. 软切换 + UI warning | 切完后旧 chunk 还是旧向量，新 chunk 用新 Embedder；维度不同时检索失败 | ✅ |
| C. 维度不同时拒绝切换 | 强一致但用户体验差 | 部分采纳（见下） |

**v1 决策（B + C 折中）**：

- **维度相同**：直接切，`PUT /v1/libraries/{lib}/settings` 200。混合向量在 Qdrant 同 collection 里共存——质量会下降，但不会崩。前端 UI 显示 warning：「该 Library 含 2 种 Embedder 产物，建议跑 Reindex」。
- **维度不同**：API 返回 `409 Conflict` + `error_code = "embedder_dim_mismatch"`，提示用户先跑 `POST /v1/libraries/{lib}/reindex` 或在前端确认「我要重建索引」。这是因为维度不同的向量根本不能共存于同一个 Qdrant collection。
- **强制 reindex**：标记为 v1.1 follow-up（M8 backlog）。届时前端发 `PUT settings` 时带 `force_reindex=true`，后端入队一个 `reindex_library` 任务（worker job），状态机进入 `Indexing`（ADR-0013），完成后切换实际生效。

理由：v1 用户量极小（α 测试 5 人），切 Embedder 是个稀有的高级操作；为它建一整套 reindex pipeline 性价比低。给到 warning 信号，让用户在自己掌控的时机决定是否 reindex，比强制阻塞要研究友好。

### 7. 配置变更审计

每次 `update()` / `reset()` 在写库的同一事务里发一条 `library_config_updated` 事件到 ADR-0014 Activity Log：

```python
async with conn.transaction():
    await conn.execute("UPDATE library_config SET overrides = $1, ...")
    await activity_logger.record(
        library_id=library_id,
        type="library_config_updated",
        title=f"Configuration updated by {updated_by}",
        payload={"changed_fields": list(patch.model_fields_set)},
    )
```

不记录 before/after 的具体值（payload 可能含敏感字段如 `daily_cost_cap_usd`，且日志体积放大）。如果用户需要回溯具体改了什么，PRD §14 已经把"审计完整性"列为 v1.1+ 范畴。

### 8. 失败模式 — Postgres 不可达时降级到全局默认

这是 v1 关于「正确性 vs 可用性」最重要的取舍：

```python
async def get(self, library_id: str) -> LibraryConfig:
    try:
        row = await self._fetch_one(library_id)
    except (asyncpg.PostgresConnectionError, TimeoutError) as e:
        logger.error("library_config fetch failed; falling back to global", exc_info=e)
        await self._notifier.send(
            severity="warning",
            type="alert_triggered",
            title="LibraryConfigStore unreachable; using global defaults",
        )
        return LibraryConfig(library_id=library_id, updated_at=datetime.now(UTC))
    return _row_to_config(row)
```

理由：Postgres 短暂不可达时，让查询照常执行（用全局 default）比让所有 QA 401/503 要好。但**必须 emit alert** 让运维感知到。这条规则不适用于 `update()` —— `update` 在 Postgres 不可达时**必须失败**，不能假装写成功。

## Consequences

### Positive

- **零 migration 摩擦**：加新 override 字段只改 Pydantic 模型，DB 端 schema 不动。
- **删 Library 干净**：ON DELETE CASCADE，配置随 Library 蒸发，符合 ADR-0003 的「purge = drop everything」语义。
- **解析便宜**：单 row JSONB 读 + Pydantic 解析，p99 < 2 ms；不需要缓存层。
- **前端契约简单**：`GET /v1/libraries/{lib}/settings` 直接返回 `LibraryConfig` JSON；前端直接在表单里 round-trip 这个对象。

### Negative

- **JSONB 没有列级 NOT NULL 检查**：未来若加「必填 override 字段」，需要在 Pydantic 端硬编码 validation；DB 不护栏。
- **没有变更历史**：用户改坏了无法 1-click rollback。v1 接受这个代价；用户可手动 reset。
- **混合维度的 Qdrant collection** 是个 known quality issue（Embedder 维度相同但 distribution 不同时，召回会下降）。需要 ADR-0018 Reranker 来缓解。

### Risks

| ID | 风险 | 缓解 |
|---|---|---|
| C01 | JSONB 数据 schema drift（旧行被新代码读出来字段不全） | Pydantic 默认值 + `model_config = ConfigDict(extra="ignore")`；写入时统一用最新模型序列化 |
| C02 | Postgres 短暂不可达导致全 LLM 调用走全局 default，产生意外 cost burst | §8 中的降级策略 emit alert；ADR-0015 daily cost cap 兜底 |
| C03 | `daily_cost_cap_usd = 0` 与 `daily_cost_cap_usd = None` 容易被误用 | Pydantic validator：`Decimal('0')` 视作"无配额"明确告警；推荐用户用 `None` 表示不设上限 |
| C04 | 切 Embedder 维度相同但语义不同（如 `bge-m3` ↔ `qwen3-embedding`），用户不知情 | UI 显式 warning + Activity Log 留痕；v1.1 提供「Reindex」按钮 |

## Alternatives Considered

| 选项 | 描述 | 拒绝原因 |
|---|---|---|
| **平铺列** | 每个 override 字段一个 `library_config.llm_primary TEXT`、`embedder_name TEXT`、… | 加字段必走 alembic；无法表达嵌套结构（如 `LLMRouterSpec.fallback: list`）；NULL 与「显式空值」混淆 |
| **独立 settings 表 + 关系映射** | `library_settings(library_id, key, value_json)` EAV 形态 | 查一次 effective 要 N 次行读；类型安全靠应用层；过度泛化 |
| **配置版本化（version 列）+ history 表** | 每次 update 写新 version，老 version 进 history | v1 没有 rollback 用例；历史表本身需要保留期策略；超额复杂度 |
| **YAML 文件 per-Library**（仿 schema_yaml_path） | 每个 Library 一个 `config.yaml` | 在 Web UI 编辑很丑；多机器部署同步麻烦；JSONB 在 Postgres 已经是同等表达力 |
| **写穿到 Settings 单例热替换** | Library override 时 mutate 全局 Settings 的某个 dict | 全局可变状态 = 并发噩梦；违反不可变原则 |
| **Redis HSET per-Library** | 速度快 | 持久化弱（M7 不要求 Redis 持久化）；`updated_at + updated_by` 难维护 |

## Open Questions

1. **Embedder 切换是否要触发 status = Indexing？**（与 ADR-0013 联动）
   - 倾向：是。`PUT settings` 中含 `embedder_override` 变更时，状态机进入 Indexing，直到 reindex 完成。但 v1 不实现 reindex，所以这条是 v1.1 的事。
2. **per-Library schema_yaml_path 改动是否要触发 KG 重建？**
   - v1 不自动触发；UI 只 warning。手动跑 `POST /v1/libraries/{lib}/kg/rebuild`。
3. **是否要给「fallback chain」加合法性校验**（fallback 中的模型名都要在 LLM Gateway 已注册）？
   - v1 校验：`update()` 时调 `LLMGateway.list_models()` 比对，未注册模型直接 422。
4. **`updated_by` 怎么填？**
   - v1 单租户、无真实身份，统一填 `"api_key"`（已认证）或 `"anonymous"`（未认证）；CLI 路径填 `"cli"`。M8+ 多用户时改。

## Relationship to Other ADRs

- **ADR-0003** — Library 是数据维度。本 ADR 完全继承：`library_config` 表 PRIMARY KEY 是 `library_id`，Protocol 首参 `library_id`，无 list 重载，无跨库读取。
- **ADR-0011**（通知中心）— 配置变更 emit `library_config_updated` Notification，让用户在多设备/多 tab 间感知到。
- **ADR-0013**（Library 状态机）— Embedder 切换可能进入 Indexing 状态（v1.1 起）。
- **ADR-0014**（Activity Log）— 配置变更落一条 activity 事件。
- **ADR-0015**（Daily Cost Cap）— `daily_cost_cap_usd` 字段是 ADR-0015 的承载。LLM Gateway 在 cap 检查时调 `resolve_effective` 取该字段。
- **ADR-0007**（M7 Error Envelope）— 维度不匹配时返回 `code = "embedder_dim_mismatch"`，遵循统一错误信封。

## References

- BACKEND_ROADMAP.md §2.4（per-Library 配置存储与读取）
- BACKEND_ROADMAP.md §6 — P1 列表
- PRD §14.2 D7.6（per-Library 配置覆盖）
- PRD §16.6（Library 维度纪律）
- CODING_STANDARDS §6.5 / §12.5 / §13.5（Library 维度硬规矩）
- 实现位置：
  - `packages/core/models.py` — `LibraryConfig`、`LibraryConfigPatch`、`EffectiveLibraryConfig`
  - `packages/core/library_admin.py` — `LibraryConfigStore` Protocol + `resolve_effective`
  - `packages/storage/postgres/library_config_store.py`（新）— Postgres 适配器
  - `apps/api/routes/library_settings.py`（新）— `GET/PUT /v1/libraries/{lib}/settings`
  - `migrations/00X_library_config.sql`（新）

---

**Decision owners**: Architect
**Review cycle**: 在 ADR-0015 实现完成后回看本 ADR 的 "失败模式" 决策；M8 多租户化前回看 `updated_by` 字段语义。
