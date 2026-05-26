# ADR-0023: ⌘K 跨资源搜索的边界与 §16.6 例外条款

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M3 / M7 D7.8 — `⌘K` 命令面板 Overlay；BACKEND_ROADMAP §4.3
**Related**: ADR-0003 (Library as data partition), ADR-0014 (Activity Log — §16.6 例外的同类), ADR-0011 (Notification Center), ADR-0021 (Eval Alerts cross-Library view)
**Supersedes**: none

## Context

PRD §14.3 D7.8 / §6 写明：

> `⌘K` 命令面板 Overlay：全局唤起，搜索 Library / 文档 / 实体 / 任务 / 设置；
> 支持快速跳转与命令执行

PRD §6 「Keyboard-native」 是设计原则之一 — `⌘K` 是这一原则的旗舰实现，
跨资源搜索是用户从「这个 Library」跳到「那个 Library」、从「Library 列表」
跳到「某个文档详情」的核心导航器。

但这与 PRD §16.6 「Library 维度纪律」 看似冲突：

> L1–L4（数据层 / 检索层）：Protocol 方法跨 Library 时首参 `library_id`，
> **不接受 `library_ids: list`**；适配器按 `library_id` 物理隔离

`⌘K` 要搜索 Library 名（用于切库），意味着至少有一类查询是**不绑定单个
library_id 的**。这是不是越权？

`BACKEND_ROADMAP §4.3`（行 786–811）已明确点名本 ADR：

> ADR-0023 ⌘K 跨资源搜索 — 跨库搜索 library 名是否破坏 §16.6
> （结论：library 元数据本就不属于"数据"，类比 file system 的 directory
> listing，明确写入例外条款）

PRD §16.6 自己也在「L5（编排层）例外」段已经埋下伏笔：

> L5（编排层）例外：允许组合**只读元视图**，例如：
> - 跨 Library 活动流 …
> - Library 列表与 Stats 总览
> - Eval Dashboard 的 Library 过滤器
> - **⌘K 命令面板的全局搜索（Library / 任务 / 实体名）**
> 这些视图必须**只读**、**用户身份范围内**，不得从中触发跨 Library 的数据
> 查询或写入。

但 PRD §16.6 没有定义「实体名搜索」是否真的跨库。如果跨库搜实体名意味着
跨库 Neo4j 查询，那就违反 L1–L4 的硬约束。

需要一份 ADR 把「⌘K 搜哪些资源 / 哪些资源跨库 / 哪些资源限本库 / 为什么」
彻底敲定，避免后续实现走偏。

仍未决的设计点：

1. **4 类资源（entity / document / library / action）的搜索范围**
2. **§16.6 的边界论证** — 哪些跨库搜索合规
3. **响应模型 + 端点设计** — 单端点还是 4 端点
4. **性能预算** — 4 路并行查询的总时延
5. **排序逻辑** — 跨类型如何加权
6. **action 注册表** — 静态还是动态、命名规则、参数注入
7. **风险** — 越权 / 短查询噪声 / 多租户演进

## Decision

### 1. 4 类资源的搜索范围（关键）

| 资源类型 | 范围 | 数据源 | 是否跨 Library | §16.6 合规依据 |
|---|---|---|---|---|
| `entity` | **仅当前 library** | Neo4j name + alias fuzzy | ✗ 不跨 | L4 数据查询，必须 per-library |
| `document` | **仅当前 library** | BM25 标题字段 | ✗ 不跨 | L4 数据查询，必须 per-library |
| `library` | **跨所有用户可见 library** | Postgres ILIKE on `name`/`description`/`slug` | ✓ 跨 | L5 元视图（库元数据 ≠ 库内数据） |
| `action` | **静态注册表** | 内存常量 | N/A（无 library 维度） | 与数据层无关 |

**这是本 ADR 最核心的决策**：`entity` 和 `document` 严格 per-library，**不跨**；
`library` 跨库但只查元数据；`action` 是无状态静态表。

请求示例：

```
GET /v1/search?q=transformer&library_id=lib_abc&types=entity,document,library,action&limit=20
```

后端按 `types` 参数并行 4 路查询：

| Path | 数据源 | 是否被 library_id 限定 |
|---|---|---|
| entity | Neo4j composite DB `lib_abc__kg` | 是（Neo4j 物理分离） |
| document | BM25 index `lib_abc__corpus` | 是（OpenSearch 物理分离） |
| library | Postgres `libraries` 全表 ILIKE | 否（这是元视图） |
| action | 内存静态表 | 否（与库无关） |

### 2. §16.6 例外的边界论证

**核心论点**：library 元数据 ≠ Library 内的数据。

类比文件系统：

| 文件系统操作 | RAG-KG 类比 | §16.6 评估 |
|---|---|---|
| `ls /libraries/` | 列举 library names | 合规 — 元视图 |
| `ls /libraries/A/` | 列举 A 库的文档 | 合规 — 仍 per-library |
| `cat /libraries/A/doc1` | 查 A 库某文档 | 合规 — per-library |
| `grep -r "x" /libraries/` | **跨库搜内容** | **违规** — 跨库数据查询 |

`⌘K` 搜 library 名 = `ls /libraries/ | grep <name>`，是元视图扫描；
`⌘K` 搜 entity 名 ≠ 跨库 — 受当前 library_id 限定，仍然 = `grep <name>
/libraries/<current>/entities/`。

**判定原则**（落入开发者 review checklist）：

1. **是元数据还是内容数据？** 元数据（库名、库描述、活动日志、KPI）允许
   跨库；内容数据（chunk / triple / entity / community）必须 per-library。
2. **是只读查询还是触发计算？** 只读元视图允许；任何会触发 LLM/Embedder
   计算的查询不得跨库。
3. **是否在用户身份可见范围？** v1 单租户假设范围 = 全部库；M8 多租户后
   范围 = 用户的 library 集合。

**library 元数据被允许跨库 query 的 4 个具体字段**：

- `libraries.name`
- `libraries.description`
- `libraries.slug`
- `libraries.primary_language`（BACKEND_ROADMAP §4.1 Gap 1）

其他字段（`libraries.daily_cost_cap_usd` 等敏感配置）**不进搜索索引**。

### 3. 响应模型

```python
# packages/core/models.py
class SearchHit(BaseModel):
    type: Literal["entity", "document", "library", "action"]
    id: str                          # 资源 ID（doc_id / library_id / entity_id / action_id）
    title: str                       # 主显示文本
    subtitle: str | None = None      # 副显示文本（如 entity 的 type；document 的 author + year）
    library_id: str | None = None    # entity / document 必填；library / action 为 None
    score: float                     # 归一化分 [0, 1]
    deeplink: str                    # 前端路由（如 "/lib/abc/docs/doc123"）
    metadata: dict = {}              # 类型特定的额外字段（如 entity.label / doc.section_count）

class SearchResponse(BaseModel):
    query: str
    library_id: str | None
    hits: list[SearchHit]
    timing_ms: dict[str, int]        # {"entity": 45, "document": 80, "library": 12, "action": 1, "total": 95}
    degraded: list[str] = []         # 降级的 source（超时返回的）
```

`deeplink` 是前端路由，让 SearchHit 自带导航能力 — 用户回车即跳，无需前端
重新计算路径。

### 4. 端点设计 — 单端点 + types 参数

**单端点**：

```
GET /v1/search
  ?q=string                    # required, min 2 chars
  &library_id=lib_abc          # optional; absent = no entity/document search
  &types=entity,document,library,action  # default = all 4
  &limit=20                    # default 20, max 50
```

**为什么不分 4 个端点**：

- 前端实现：`⌘K` 只发 1 次请求，结果合并显示，逻辑简单；4 端点要并发 +
  合并 + 错误处理重复 4 次
- 后端实现：4 路查询用 `asyncio.gather`，单端点反而更直接；4 端点会
  违反 DRY（types 解析、limit 分配、score 归一都是共用代码）
- 缓存：单端点请求级 LRU 即可；4 端点缓存键设计要重做

**为什么不做 SSE 流式返回**（即「先到先吐」）：

- ⌘K 用户体感是「输完 1 个字符等结果」；总时延 ≤ 300ms 内，流式收益小
- SSE 协议复杂度（与 ADR-0007 SSE 通道独立）
- 4 路查询差距通常 < 100ms，分先后吐意义不大

**library_id 缺失时的行为**：

```python
# 用户在 Library 列表页 ⌘K（无 current library）
GET /v1/search?q=transformer&types=library,action

# entity / document 类型在无 library_id 时返回空（不报错）
GET /v1/search?q=transformer  # default types=all
→ {
    "hits": [
        {"type": "library", ...},
        {"type": "action", ...}
    ],
    "degraded": ["entity:no_library_context", "document:no_library_context"]
}
```

### 5. 性能预算

| 路径 | p95 预算 | 兜底 |
|---|---|---|
| `entity` (Neo4j fuzzy on name + alias) | 80 ms | 超时返回 0 hits，标 `degraded` |
| `document` (BM25 title) | 100 ms | 同上 |
| `library` (Postgres ILIKE on 4 列) | 30 ms | 同上 |
| `action` (内存模糊匹配) | 5 ms | 不会超时 |
| **总（4 路并行）** | **≤ 300 ms p95** | 任一超时单独 fail，其他正常返回 |

实现：

```python
async def search(req: SearchRequest) -> SearchResponse:
    timeout = req.timeout_ms or 300
    deadline = time.monotonic() + timeout / 1000

    tasks = []
    if "entity" in req.types and req.library_id:
        tasks.append(("entity", search_entities(req.q, req.library_id, req.limit)))
    if "document" in req.types and req.library_id:
        tasks.append(("document", search_documents(req.q, req.library_id, req.limit)))
    if "library" in req.types:
        tasks.append(("library", search_libraries(req.q, req.limit)))
    if "action" in req.types:
        tasks.append(("action", search_actions(req.q, req.limit)))

    results = await asyncio.gather(
        *(asyncio.wait_for(t, timeout=max(deadline - time.monotonic(), 0.05))
          for _, t in tasks),
        return_exceptions=True,
    )

    hits, degraded, timings = [], [], {}
    for (kind, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            degraded.append(f"{kind}:{type(result).__name__}")
            continue
        hits.extend(result.hits)
        timings[kind] = result.duration_ms

    return SearchResponse(
        query=req.q,
        library_id=req.library_id,
        hits=normalize_and_rank(hits, req.limit),
        timing_ms=timings,
        degraded=degraded,
    )
```

前端配 200 ms debounce（BACKEND_ROADMAP §7 BR10 缓解）— 用户输完 2 个字符
之后停顿 200ms 才发请求，避免每个 keystroke 一次请求。

### 6. 排序逻辑（跨类型加权 + 同类型按 score）

每路查询返回的 hits 各自在 `[0, 1]` 范围内（路径内部归一）。跨类型再加权：

```python
TYPE_WEIGHTS = {
    "action":   1.10,   # 命令优先 — 用户主动检索动作
    "library":  1.00,   # 中性
    "entity":   0.95,   # 略低于 library（entity 噪声多）
    "document": 0.90,   # 最低（document 数量大，信号噪比低）
}

def normalize_and_rank(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    weighted = [
        hit.model_copy(update={"score": hit.score * TYPE_WEIGHTS[hit.type]})
        for hit in hits
    ]
    return sorted(weighted, key=lambda h: h.score, reverse=True)[:limit]
```

**为什么 action 加权最高**：当用户输入 "open" / "settings" / "review" 等关键词，
匹配的几乎一定是 action — 不让 entity / document 的高 BM25 分稀释 action
的重要性。

权重数字是经验起点，校准方法：

- 每月用 Langfuse 看 `⌘K` 选中分布，按类型统计 `selected / shown`
- 若某类型 CTR 显著低于按 score 占比应有的 CTR，调权重
- 调整需进 ADR amendment（避免静默漂移）

### 7. Action 注册表

```python
# apps/api/search_actions.py
@dataclass(frozen=True)
class Action:
    id: str
    title: str
    subtitle: str | None
    keywords: tuple[str, ...]      # 关键词扩展，匹配时合并
    deeplink_template: str         # "/lib/{library_id}/chat" or "/settings"
    requires_library: bool = False

ACTIONS: tuple[Action, ...] = (
    Action(
        id="open_chat",
        title="Open Chat",
        subtitle="Start a new conversation in this library",
        keywords=("chat", "qa", "ask", "question"),
        deeplink_template="/lib/{library_id}/chat",
        requires_library=True,
    ),
    Action(
        id="generate_review",
        title="Generate Literature Review",
        subtitle="Run a review task on this library",
        keywords=("review", "survey", "literature", "summary"),
        deeplink_template="/lib/{library_id}/review/new",
        requires_library=True,
    ),
    Action(
        id="open_kg",
        title="Open Knowledge Graph",
        subtitle="Explore the KG of this library",
        keywords=("kg", "graph", "knowledge"),
        deeplink_template="/lib/{library_id}/kg",
        requires_library=True,
    ),
    Action(
        id="open_eval",
        title="Open Eval Dashboard",
        subtitle="View VAR / Citation F1 / cost trends",
        keywords=("eval", "evaluation", "metrics", "var", "kpi"),
        deeplink_template="/lib/{library_id}/eval",
        requires_library=True,
    ),
    Action(
        id="settings_global",
        title="Open Global Settings",
        subtitle="Configure backend, LLM, embedder",
        keywords=("settings", "config", "preference"),
        deeplink_template="/settings",
        requires_library=False,
    ),
    Action(
        id="library_create",
        title="Create New Library",
        subtitle="Add a new research library",
        keywords=("new", "create", "library", "+"),
        deeplink_template="/libraries/new",
        requires_library=False,
    ),
    Action(
        id="open_documents",
        title="Open Documents",
        subtitle="Browse documents in this library",
        keywords=("docs", "documents", "papers", "files"),
        deeplink_template="/lib/{library_id}/docs",
        requires_library=True,
    ),
    Action(
        id="open_hypothesize",
        title="Generate Hypotheses",
        subtitle="Run hypothesis generation on entity pairs",
        keywords=("hypothesis", "hypothesize", "novel", "ideas"),
        deeplink_template="/lib/{library_id}/hypothesize",
        requires_library=True,
    ),
)
```

匹配实现：

```python
def search_actions(q: str, limit: int, library_id: str | None = None) -> SearchResult:
    q_lower = q.lower()
    candidates = []
    for action in ACTIONS:
        if action.requires_library and not library_id:
            continue
        score = score_action_match(action, q_lower)
        if score == 0.0:
            continue
        candidates.append((action, score))

    candidates.sort(key=lambda t: t[1], reverse=True)
    return SearchResult(
        hits=[
            SearchHit(
                type="action",
                id=a.id,
                title=a.title,
                subtitle=a.subtitle,
                library_id=None,
                score=s,
                deeplink=a.deeplink_template.format(library_id=library_id or ""),
                metadata={"keywords": list(a.keywords)},
            )
            for a, s in candidates[:limit]
        ],
        duration_ms=...,
    )

def score_action_match(action: Action, q_lower: str) -> float:
    tokens = q_lower.split()
    haystacks = (action.title.lower(), *(k.lower() for k in action.keywords))
    matched = sum(
        1 for t in tokens if any(t in h for h in haystacks)
    )
    if matched == 0:
        return 0.0
    return min(matched / max(len(tokens), 1), 1.0)
```

「静态注册表」选择理由：

- v1 action 数量 < 20，硬编码维护成本极低
- 动态注册（如插件机制）是 v2+ 工作（与 PRD §15.2 v2 候选「插件市场」联动）
- 静态表无 DB 依赖、零冷启动、易于 grep

### 8. 字段最小长度约束 — `q.length ≥ 2`

```
GET /v1/search?q=a   →  400 ErrorEnvelope { code: "invalid_query", message: "Query must be at least 2 characters" }
GET /v1/search?q=ab  →  200 ...
```

为什么 2 字符：

- 1 字符在 BM25 / Neo4j fuzzy 上几乎全匹配（噪声爆炸）
- 中文 1 字符就有意义？— 选择 2 字符是英文领域的妥协；中文用户多用「图谱」
  「假设」等 2 字以上词，影响小

### 9. v1 单租户假设 + M8 多租户演进

v1 单租户：search 跨 Library 等于「跨用户全部 Library」。

M8 多租户演进路径：

```python
async def search_libraries(q: str, limit: int, principal: Principal) -> SearchResult:
    # v1: principal 总是 anonymous 或 admin，可见所有库
    if principal.kind == "admin":
        libs = await libraries_repo.search_all(q, limit)
    else:
        # M8: 引入 user_library_membership 表
        libs = await libraries_repo.search_for_user(principal.user_id, q, limit)
    return SearchResult(...)
```

**v1 不实现 user_library_membership**，但 search_libraries 接口签名预留 `principal`
参数（与 `apps/api/auth.py` get_current_principal 对齐），M8 时只动 SQL 不动
API 契约。

### 10. 实现位置

```
apps/api/routes/search.py            # GET /v1/search
apps/api/search_actions.py           # ACTIONS 静态注册表
apps/api/search_normalize.py         # 跨类型加权 + 排序

packages/retrieval/searchers/
├── entity_searcher.py               # Neo4j name + alias fuzzy（限定 library）
├── document_searcher.py             # BM25 title（限定 library）
└── library_searcher.py              # Postgres ILIKE on 元数据（跨库）

packages/core/models.py              # SearchHit / SearchResponse / SearchRequest
```

**为什么 `library_searcher` 在 packages/retrieval 而不是 packages/library_admin**：

- 它是只读查询（无写入），与 retrieval package 性质一致
- library_admin 是 CRUD + lifecycle（创建 / 删除 / status 巡检），写多读少
- 二者依赖方向同向（`retrieval/library_searcher → core models → libraries 表`）

但 `library_searcher` 的实现**不调用 `LibraryRepository.find_by_id`**（per-library
读），而是新增 `LibraryRepository.search_metadata(q, limit)` —
明确这是**元视图查询**，与 per-library CRUD 方法分开。

### 11. 与 ADR-0014 Activity Log 的一致性

ADR-0014（Activity Log 设计 — 见 BACKEND_ROADMAP §6.2 P1 排期 #8）也是 §16.6
的 L5 例外：跨 Library 的活动流。本 ADR 与 ADR-0014 在结构上同构：

| 维度 | ADR-0014 Activity Log | ADR-0023 ⌘K Search |
|---|---|---|
| §16.6 例外类型 | L5 元视图 | L5 元视图 |
| 跨 Library 范围 | 全部用户可见 library | 全部用户可见 library |
| 数据性质 | 元数据（操作记录） | 元数据（库名/描述） + per-library 数据查询 |
| 写入触发 | 任务完成 / 状态变更 | 不写入（纯只读） |
| 多租户演进 | M8 加 user_id 过滤 | M8 加 user_id 过滤 |

两者共同确立了 §16.6 例外条款的「元视图」准则 — 后续新增类似端点（如
M8 的全局通知中心、跨 Library KPI 总览）应当引用本两条 ADR 作为先例。

### 12. 不引入 Elasticsearch / Meilisearch

v1 直接查 Postgres + Neo4j + BM25 实例（已存在），**不引入新搜索基础设施**：

- 数据规模：单 Library 文档 ≤ 10k，全库 library 数量 ≤ 100，Postgres ILIKE
  + LIMIT 20 在 ms 级
- 已有 BM25（`packages/indexing/bm25_adapter.py`）已经覆盖 document 搜索
- 已有 Neo4j fuzzy match 已经覆盖 entity 搜索
- Elasticsearch / Meilisearch 的优势在于 1M+ 文档、高基数 facet、复杂 ranker
  — 本场景全部用不到

Open Question §3：v1.1 数据规模超 100k 时再评估。

## Consequences

### Positive

- **§16.6 边界明确化** — 哪些跨库查询合规、哪些违规，写进 ADR 可 reference。
- **单端点简化前端** — `⌘K` 一个 fetch，前端 200 行 Vue 组件搞定。
- **4 路并行高性能** — p95 ≤ 300ms 对键盘交互足够。
- **降级友好** — 单路超时不影响其他路的结果，前端可显示「搜索 entity
  超时，但 library / action 已展示」。
- **action 静态表 zero infra** — 没有 DB 依赖，CI 中即可单元测。
- **多租户演进零迁移** — `principal` 参数已预留。
- **与 ADR-0014 同构** — 后续新增 §16.6 例外有先例可循。

### Negative

- **跨库 library 元数据搜索** 在 multi-tenant 下要补 user_library_membership
  过滤 — v1 没这层保护，**对单租户假设依赖很重**。M8 之前不能贸然向公网
  暴露此端点。
- **action 静态表** 添加 / 修改要改代码 + 部署 — 不像数据库表那样支持热加载。
  v1 接受（变更频率低）。
- **类型权重经验数字** 0.90/0.95/1.00/1.10 是拍脑袋的；只能等线上数据校准。
- **q.length ≥ 2** 对中文用户是宽松的，但对英文 1 字母（"a" / "i"）查询不
  友好；BACKEND_ROADMAP §7 BR10 已记。

### Risks

| 风险 | 缓解 |
|---|---|
| 4 路并行 N+1 慢（BACKEND_ROADMAP §7 BR10） | 4 路并行 + 单路超时降级；前端 200 ms debounce |
| 短查询噪声 | `q.length ≥ 2` 硬约束；< 2 字符返回 invalid_query 错误 |
| 跨库 library 元数据搜索 → 越权（M8 多租户） | v1 单租户假设；M8 引入 user_library_membership 过滤；本 ADR §9 已留接口 |
| Neo4j 跨 library composite DB 误用 | `entity_searcher` 强制传 library_id；调用方未传 → 编译期错误（Pydantic required） |
| 用户期望「跨库搜文档内容」 → 失望 | UI 在搜索框 placeholder 写「Search this library + jump anywhere」；明确范围 |
| Action 注册表与前端路由 drift | 后端 `/v1/search/actions/manifest` 暴露 ACTIONS 列表；前端启动时校验 deeplink_template 模板与 router 匹配 |
| Elasticsearch 早期不引入 → 性能瓶颈 | 当 single-Library doc 数 > 100k 时再评估（保留为 Open Question §3） |
| ⌘K 暴露 library 列表给非授权用户 | v1 单租户；M8 RBAC：principal.user_id → user_library_membership |

### Trade-offs

**为什么不分 4 个端点**（`/v1/search/entities`, `.../documents`, `.../libraries`,
`.../actions`）：

- 前端复杂度 4 倍（4 个 fetch + 合并 + 错误处理）
- 后端 DRY 损失（types 解析、limit 分配、score 归一各重复 4 次）
- 缓存键设计复杂
- 当某 type 的查询模式有特殊需求（如 entity 要求 confidence > 0.8）才该
  分端点；当前 4 类需求高度相似，单端点合适

**为什么 `library` 跨库但 `entity` / `document` 不跨**：

- library 元数据是 §16.6 明确允许的「只读元视图」
- entity / document 是 L4 数据 — 跨库会调用 N 个 Neo4j composite DB / N 个
  BM25 index，不仅违反 §16.6 还有性能问题（O(N) 查询）

**为什么 `q.length ≥ 2`**：

- 1 字符匹配返回 ~50% 的索引项，前端无法渲染
- 改为 3 字符对中文用户太严
- 2 是平衡点

**为什么不上 Elasticsearch**：

- v1 数据 volume 不够大（< 10k docs / library，< 100 libraries）
- 引入新基础设施 = 新 ops / 新依赖 / 新备份链路
- Postgres + BM25 + Neo4j 已能覆盖，且都是已有依赖

**为什么 action 加权 1.10 而 entity 0.95**：

- action 是用户**主动检索**的命令 — 输 "review" 时几乎肯定要 generate review
- entity 噪声多（一个 entity 可能在多文档出现）
- document 更噪（数量大、标题信号弱）
- 权重差距 ≤ 20%，避免某类完全压制其他类

## Alternatives Considered

| 方案 | 拒绝原因 |
|---|---|
| 4 个独立端点 | 前后端复杂度 4×；DRY 损失；当前需求统一 |
| 跨库 entity / document 搜索 | 违反 §16.6；O(N libraries) 查询慢 |
| 引入 Elasticsearch | 数据 volume 不够大；新基础设施成本 |
| Action 动态注册（DB 表 / 插件） | v1 数量 < 20 ，硬编码够；动态是 v2 插件市场工作 |
| 流式 SSE 返回 | 总时延 < 300ms ，流式收益小；协议复杂 |
| 不做跨库 library 搜索（强行 §16.6 字面解读） | `⌘K` 切库要拉全 library 列表前端过滤 → 用户体验差 |
| `q.length ≥ 1` | 1 字符噪声爆炸 |
| 加权 sum vs max | 跨类型 max 让某类完全压制其他类；加权 sum 平衡 |
| 取消 library 类型，只搜 entity / document / action | `⌘K` 切库是核心 UX，不能砍 |
| 把 search 放进 packages/orchestration | 它是只读查询，不是任务编排；放 retrieval 更合适 |

## Open Questions

1. **多租户 principal 校验** — M8 引入 user_library_membership 时，library_searcher
   是按 user_id JOIN 还是按 explicit list 过滤？取决于 RBAC 模型。
2. **action 注册表的国际化** — 当前 title / subtitle 是英文硬编码；中文用户
   习惯否？若需要 i18n，需引入翻译机制（与 PRD §6 设计原则的一致性评估）。
3. **数据规模触及 Elasticsearch 阈值** — 单 library doc > 100k 或 library 总数 >
   1k 时再评估，本 ADR 保留接口。
4. **快捷键预设** — `⌘K` 之外是否还要 `⌘P`（document 优先）/ `⌘E`（entity
   优先）？v1 不做，看用户反馈。
5. **历史搜索记录** — 是否在 `⌘K` 顶部展示「最近搜索」（与浏览器 history 类似）？
   当前不做（隐私顾虑 + sqlite 写入风险），v1.1 评估。
6. **类型权重的自动调优** — §6 的权重数字依赖人工校准；是否引入 bandit
   机制根据用户点击率自适应？v1 不做（增加复杂度，收益未知）。

## 与其他 ADR 的关系

- **ADR-0003 Library as data partition** — 本 ADR 把 §16.6 的「⌘K 命令面板的全局
  搜索（Library / 任务 / 实体名）」例外条款落地，完全遵守 ADR-0003 物理隔离
  原则（entity / document 仍 per-library）。
- **ADR-0014 Activity Log** — 跨 Library 元视图的同类先例；二者共同确立
  「元数据搜索 + 元视图聚合」是 §16.6 允许的；后续类似端点应 cross-reference
  这两条。
- **ADR-0011 Notification Center** — 通知列表的跨 Library 视图（`GET /v1/notifications`
  无 library_id 限定）也是同类例外，但本 ADR 不重复定义 — 由 ADR-0011 自身
  承载。
- **ADR-0021 Eval Alerts** — `GET /v1/alerts?status=active` 的跨库 endpoint 是
  同类例外，参考本 ADR 的 §16.6 边界论证。
- **ADR-0007 Error Envelope** — `q.length < 2` 返回的 `invalid_query` ErrorCode
  应注册到 `packages/core/api_errors.py`；本 ADR 不重新定义错误格式。
- **ADR-0008 Context Management** — Conversation list 在左侧栏（PRD §6 S3 Chat），
  其搜索应当走本 ADR 的 search 端点 type=conversation 扩展？v1 不做（conversation
  在 chat 屏自带搜索框），保留为 v1.1 评估。

## References

- PRD §6 Keyboard-native 设计原则（⌘K 旗舰实现的渊源）
- PRD §14.3 D7.8（⌘K 命令面板验收要求）
- PRD §16.6 Library 维度纪律（L5 例外条款 — 「⌘K 命令面板的全局搜索」明文写入）
- PRD §16.6 Library 维度纪律（L1–L4 不接受 `library_ids: list` — 本 ADR 不破坏此约束）
- BACKEND_ROADMAP §4.3（实现位置定义）
- BACKEND_ROADMAP §7 BR10（4 路并行 N+1 慢 — 缓解依据）
- BACKEND_ROADMAP §6.2 P1 排期 #16（⌘K Search endpoint 工作量）
- `apps/api/routes/search.py`（新）
- `apps/api/search_actions.py`（新 — ACTIONS 注册表）
- `apps/api/search_normalize.py`（新 — 跨类型加权排序）
- `packages/retrieval/searchers/entity_searcher.py`（新）
- `packages/retrieval/searchers/document_searcher.py`（新）
- `packages/retrieval/searchers/library_searcher.py`（新）
- `packages/core/models.py` — `SearchHit`, `SearchResponse`, `SearchRequest`
- ADR-0003 — Library as data partition
- ADR-0014 — Activity Log（同类 §16.6 例外的先例）
