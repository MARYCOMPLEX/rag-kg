# ADR-0020: Hypothesis 三维评分公式（novelty / confidence / verifiability）

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M5 D5.3 — 假设生成的 KPI；S7 Hypothesize UI
**Related**: ADR-0003 (Library partition), ADR-0006 (Local vs Global routing), ADR-0008 (Context Management — embeddings reuse), ADR-0016 (VAR), ADR-0021 (Eval Alerts)
**Supersedes**: none

## Context

PRD §12.3 D5.3 要求：

> 5 个实体对各产出 ≥ 3 个合理假设；每条带 `novelty / confidence / verifiability`
> 三维评分。

PRD §12.2 给出粗略口径（"novelty = embedding 距离 + 引用计数反向 / confidence =
KG 路径数 × 路径置信度的几何均值 / verifiability = 路径上是否含 Method/Dataset
节点"），但**没有定义可实现的精确公式**：

- `novelty` 用什么距离度量、参考集合是什么、如何归一到 `[0,1]`？
- `confidence` 在 `paths == []` 时如何处理？空路径假设是否应当存在？
- `verifiability` 的"启发式"具体加权多少、与路径数有什么关系？
- 排序键是什么？三个维度是相加、相乘、还是带权？
- "合理假设"的硬阈值（filter）和"高质量假设"的排序键（sort）能否分离？

`BACKEND_ROADMAP §3.7 Gap 2`（行 682–706）已明确点名本 ADR：

> ADR-0020 Hypothesis 评分公式 — 三维定义、权重、与 PRD §12.3 D5.3 验收对齐

而 `BACKEND_ROADMAP §6.2 P2 排期`（行 903）把 ADR-0020 + Hypothesis 三维评分
列为 M7 nice-to-have / 可滑到 v1.1。这意味着：本 ADR 必须给出 v1 能落、
v1.1 能演进 的最小公式，避免锁死后期路径。

PRD §12.5 同时记录了两条相关风险：

- 「假设合理但无据」 — 每条假设至少 2 条 KG 路径作证据
- 「假设新但已被推翻」 — embedding 距离不能识别 retract 文献（隐含）

这两条决定了一个边界：**「证据存在」是 hard filter，不进打分；「证据强弱」
才进打分**。

S7 UI（Hypothesize 屏）需要展示 3 条进度条 + 一个排序后的列表，因此公式需要
满足：

1. 三维都在 `[0,1]`，UI 直接渲染百分比
2. 单条假设评分 ≤ 200 ms（embedding 批处理友好）
3. 公式可解释 — 用户能在 hover 上看到「为什么 novelty=0.71」

## Decision

### 1. 三维精确定义

#### 1.1 novelty ∈ [0,1]

候选假设文本 `candidate.text` 与本 Library 内**已有结论 corpus** 的 embedding
平均 cosine 距离，min-max 归一到 `[0,1]`。

```python
# packages/orchestration/tasks/hypothesis.py
def compute_novelty(
    library_id: str,
    candidate_embedding: list[float],
    reference_embeddings: list[list[float]],   # 见 §1.4 reference set
) -> float:
    if not reference_embeddings:
        return 0.5                              # 无参照系 → 中性默认
    distances = [
        1.0 - cosine_similarity(candidate_embedding, ref)
        for ref in reference_embeddings
    ]
    raw = mean(distances)                       # ∈ [0, 2]
    # min-max 归一：基于 reference set 自身的距离分布
    p10, p90 = percentiles(reference_self_distances(reference_embeddings), [10, 90])
    return clamp((raw - p10) / max(p90 - p10, 1e-6), 0.0, 1.0)
```

**关键设计**：

- **参照系 = 本 Library 的「community summaries + chunk-level claims」**，不是
  全 web。理由：跨 Library 的距离不可比（不同领域 embedding 分布不同），
  且与 ADR-0003 per-Library 物理隔离一致。
- **参照集大小**：取 `min(community_summaries.count, 200)`；超过 200 时随机
  采样（已存 embedding，无新 LLM 调用成本）。
- **min-max 归一基准**：用 reference set 内部的两两距离做 `p10 / p90`，
  使分布稳定 — 否则一个领域全是「新假设」时分数都贴近 1。
- **空 reference 兜底**：刚建库（< 5 个 community）时返回 `0.5`，UI 标
  `(insufficient baseline, n=<count>)`。

#### 1.2 confidence ∈ [0,1]

候选假设依附的所有 KG 路径的 `path.confidence` 几何均值。

```python
def compute_confidence(paths: list[ReasoningPath]) -> float:
    if not paths:
        return 0.0                              # 无路径 → 应在 filter 阶段被剔除
    confs = [p.confidence for p in paths if 0.0 < p.confidence <= 1.0]
    if not confs:
        return 0.0
    # geometric mean = exp(mean(log(c)))
    return math.exp(sum(math.log(c) for c in confs) / len(confs))
```

**为什么用 几何均值 而非 算术均值**：

- 几何均值对低值敏感 — 一条 0.2 的路径会显著拖低，符合「证据链强度由最
  弱环节决定」的直觉。
- 算术均值会被高 confidence 路径稀释掩盖弱证据。
- 若 v1.1 引入路径数加权，可改为 `weighted_geomean`，公式向后兼容。

**`paths == []` 处理**：返回 `0.0`，但**这种候选会在 filter 阶段被剔除**（见
§3 PRD §12.5 风险对齐）— 此处保留 `0.0` 仅为防御性。

#### 1.3 verifiability ∈ [0,1]

双成分加权：路径上 Method/Dataset 节点比例 × 0.8 + 路径数 × 0.2。

```python
METHOD_DATASET_LABELS = {"Method", "Dataset", "Benchmark", "Metric"}

def compute_verifiability(paths: list[ReasoningPath]) -> float:
    if not paths:
        return 0.0
    # 成分 A：路径上 Method/Dataset 节点占比
    total_nodes = sum(len(p.nodes) for p in paths)
    if total_nodes == 0:
        method_ratio = 0.0
    else:
        method_nodes = sum(
            1 for p in paths for n in p.nodes
            if n.label in METHOD_DATASET_LABELS
        )
        method_ratio = method_nodes / total_nodes
    # 成分 B：路径数（4 路径以上视为饱和）
    path_density = min(len(paths) / 4.0, 1.0)
    # 经验加权
    return clamp(method_ratio * 0.8 + path_density * 0.2, 0.0, 1.0)
```

**为什么是 0.8 / 0.2**：

- 主要因素是「这条假设到底能不能在实验台上复现」 — Method/Dataset 占比
  最直接反映这一点（占主导 0.8）。
- 路径密度是次要因素 — 多路径意味着多视角验证可能（占辅助 0.2）。
- 这两个数字是 v1 经验起点，每月用人工标注样本校准（见 §5）。

#### 1.4 reference set 选取（缓存 + 增量）

每条假设评分都重算 reference embeddings 是不可接受的。决策：

- **缓存**：`packages/orchestration/cache/novelty_baseline.py`，per-Library 一份，
  TTL 24h；写入 SQLite（`data/state/hypothesis_cache.sqlite`，与 ingest_state /
  context 分库，符合 ADR-0007 / ADR-0008 模式）。
- **增量失效**：community rebuild 完成后 `cache.invalidate(library_id)`。
- **冷启动**：第一次生成假设时同步构建 baseline（≤ 2 s for 200 summaries）。

### 2. 排序公式 — `sort_key = novelty × confidence`

```python
def sort_key(c: HypothesisCandidate) -> float:
    return c.novelty * c.confidence
```

**为什么不加入 verifiability**：

| 假设的两种类型 | novelty | confidence | verifiability | 是否值得展示？ |
|---|---|---|---|---|
| 真新颖 + 强证据 + 可验证 | 高 | 高 | 高 | ★ 展示在前 |
| 真新颖 + 强证据 + 难验证 | 高 | 高 | 低 | ★ 仍值得 — 哲学性假设也是研究输出 |
| 老调重弹 + 强证据 + 可验证 | 低 | 高 | 高 | ✗ 用户已经知道 — 不值得做假设输出 |
| 真新颖 + 弱证据 + 任意 | 高 | 低 | * | ✗ 不可信 — 不值得 |

`novelty × confidence` 是同时筛掉 第 3、4 行的最简公式。`verifiability` 作为
**第三维独立展示**（UI 上是第三个进度条），让用户判断哪些假设可以拿去做
实验、哪些只能写综述。

**乘法 vs 加法**：乘法是「与」语义 — 必须既新又有据；加法是「或」语义 —
单维高分就能上榜，会让「新但无据」的假设刷屏。乘法符合 PRD §12.5「假设
合理但无据」风险的硬约束精神。

### 3. 与 PRD §12.5 「假设合理但无据」对齐 — Filter 不算分

PRD §12.5 风险登记：

> 假设合理但无据 → 缓解：要求每条假设至少 2 条 KG 路径作证据

这是 **filter 而非 score**：

```python
MIN_PATHS_REQUIRED = 2

def filter_candidates(candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]:
    return [c for c in candidates if len(c.paths) >= MIN_PATHS_REQUIRED]
```

理由：把它做进打分会让「3 条 0.3 confidence 的路径」和「2 条 0.7 confidence
的路径」混淆 — 前者更接近「无据」。所以两步分离：

1. **Filter**（hard）：`len(paths) ≥ 2`
2. **Score**（soft）：上述三维

未通过 filter 的候选**不返回给前端**（避免界面噪音）；可在调试日志里看到。

### 4. 实现位置

```
packages/orchestration/tasks/hypothesis.py
├── score_hypothesis(library_id: str, candidate: HypothesisCandidate) -> ScoreVector
├── _compute_novelty(library_id, candidate_embedding) -> float
├── _compute_confidence(paths) -> float
├── _compute_verifiability(paths) -> float
└── _sort_key(candidate) -> float

packages/orchestration/cache/novelty_baseline.py
├── NoveltyBaselineCache  (sqlite-backed, per-library)
└── BaselineEmbedding(library_id, embedding_b64, source_kind, source_id, created_at)

packages/core/models.py
├── ScoreVector(novelty, confidence, verifiability, sort_key)
└── HypothesisCandidate (existing — see BACKEND_ROADMAP §3.7 Gap 2)
```

数据模型（落到 `packages/core/models.py`）：

```python
class ScoreVector(BaseModel):
    novelty: float                  # [0,1]
    confidence: float               # [0,1]
    verifiability: float            # [0,1]
    sort_key: float                 # novelty * confidence, denormalized for query
    baseline_size: int              # |reference set| for novelty computation
    method_node_count: int          # for verifiability transparency
    total_node_count: int

class HypothesisCandidate(BaseModel):       # extends BACKEND_ROADMAP §3.7 Gap 2
    library_id: str
    text: str
    paths: list[ReasoningPath]              # 见 BACKEND_ROADMAP §3.7 Gap 1
    evidence: list[Citation]
    score: ScoreVector
```

**SQLite schema**（`hypothesis_cache.sqlite`）：

```sql
CREATE TABLE novelty_baseline (
    library_id      TEXT NOT NULL,
    source_kind     TEXT NOT NULL CHECK(source_kind IN ('community', 'chunk_claim')),
    source_id       TEXT NOT NULL,
    embedding       BLOB NOT NULL,         -- packed float32 (4 * dim bytes)
    embedding_dim   INTEGER NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (library_id, source_kind, source_id)
);
CREATE INDEX novelty_baseline_lib_idx ON novelty_baseline(library_id);

CREATE TABLE baseline_metadata (
    library_id              TEXT PRIMARY KEY,
    last_built_at           TIMESTAMP NOT NULL,
    p10_distance            REAL NOT NULL,
    p90_distance            REAL NOT NULL,
    sample_size             INTEGER NOT NULL,
    invalidated             BOOLEAN NOT NULL DEFAULT 0
);
```

### 5. 校准方法 — 月度人工对照

每月一次：

1. **采样 50 条假设**：从过去 30 天 production 假设中分层采样（按 sort_key
   分位 5 段，每段 10 条），avoid recency bias。
2. **人工偏好排序**：研究员（≥ 2 人）独立给 50 条按「研究价值」打 1–5 分。
3. **Spearman 相关**：公式 `sort_key` 排序 vs 人工平均分排序的 Spearman ρ。
4. **目标**：`ρ ≥ 0.6`。低于 0.5 触发公式参数重审（特别是 verifiability
   的 0.8/0.2 加权）。
5. **结果落 `data/calibration/hypothesis/<yyyy-mm>.json`**，进 git。

校准报告字段：

```json
{
  "month": "2026-06",
  "sample_size": 50,
  "spearman_rho": 0.71,
  "human_judges": ["judge_a", "judge_b"],
  "inter_judge_kappa": 0.62,
  "weight_adjustments": {
    "verifiability_method_weight": {"old": 0.8, "new": 0.8, "rationale": "stable"}
  }
}
```

### 6. 性能预算

| 阶段 | 预算 | 兜底 |
|---|---|---|
| baseline cache hit | ≤ 1 ms | — |
| baseline cache miss + rebuild (n=200) | ≤ 2 s | 同步阻塞首请求；后续 24h 命中缓存 |
| 单条 candidate embedding | ≤ 60 ms | embedding 批处理（见下） |
| novelty compute (vector ops) | ≤ 5 ms | numpy 向量化 |
| confidence + verifiability | ≤ 2 ms | pure python |
| **每条假设总评分** | **≤ 200 ms** | 超时返回 partial — sort_key 默认 0 |

**embedding 批处理**：一次任务通常生成 5×3=15 条假设，应**一次 embedding 调用**
（15 条 text 一起送）。`Embedder.embed_batch(texts: list[str])` 已存在
（见 `packages/embedding/service.py`）。

### 7. 与 LLM-judge 的对照

每月一次（与 §5 校准同节奏）：

- 同一批 50 条假设送 LLM-judge（GPT-4o-mini 或 Claude-Haiku-4.5），prompt：
  「按 1–5 评估这条假设的 novelty / confidence / verifiability，分别给分」
- 对比：公式 sort_key vs LLM-judge `novelty × confidence`
- 目标：相关 ρ ≥ 0.5（弱要求；LLM-judge 本身有噪音）
- 用途：**校准 verifiability 的 0.8/0.2 系数**，不替代公式 — 这是 PRD §13.2
  「LLM-as-Judge 用于子观性问题」原则的应用，但 hypothesis 评分主路径必须
  是确定性公式（避免每次评分多花一次 LLM 调用，对 R01 成本风险敏感）。

### 8. UI 暴露

S7 屏每条 hypothesis 卡片：

```
┌────────────────────────────────────────────────────┐
│ [假设文本 200 字 ............................... ] │
│                                                    │
│ Novelty       ████████░░  82%  (n=187 baseline)    │
│ Confidence    ██████░░░░  61%  (3 paths, geomean)  │
│ Verifiability █████░░░░░  51%  (4/9 method nodes)  │
│                                                    │
│ Sort score: 0.50 = 0.82 × 0.61                     │
│ Evidence: paper_abc#§3.2, paper_xyz#§4.1           │
└────────────────────────────────────────────────────┘
```

每个进度条右侧 hover 暴露原始计算（baseline 大小 / 路径数 / 节点数），
满足 PRD §6 的「Trust through Trace」原则。

## Consequences

### Positive

- **可解释**：每个分数都对应可以指给用户看的具体计数（路径数、节点数、
  baseline 大小），非黑盒。
- **per-Library 友好**：novelty 参照系限定本库，跨库分数不强行可比，但同库
  内排序稳定。
- **零额外 LLM 成本**：评分纯本地计算（embedding 在生成阶段已算）；月度
  LLM-judge 对照才是 LLM 调用。
- **公式向后兼容**：v1.1 可加 path 数加权（geomean → weighted_geomean）、
  retract 信号、KG embedding（见 §Open Questions），不破坏 v1 字段。
- **PRD §12.3 D5.3 验收对齐**：5 实体对 × 3 假设，每条三维评分 — filter +
  score 公式直接产出。

### Negative

- **baseline 冷启动慢**：首次评分要建 200 条 baseline embedding（≤ 2 s），
  用户首请求体感稍慢。缓解：community rebuild 完成时**预热**（worker
  job 触发 baseline rebuild，下次评分命中缓存）。
- **min-max 归一对小库不稳**：community < 20 时分布失真，归一后分数贴近
  极值。缓解：`baseline_size < 20` 时关闭归一，直接用 raw distance（UI 标
  `(experimental, small baseline)`）。
- **乘法掩盖单维高光**：novelty=1.0 + confidence=0.1 → sort=0.1，看起来不
  如 0.5×0.5=0.25。是 trade-off，不是 bug — 见 §2 表格论证。

### Risks

| 风险 | 缓解 |
|---|---|
| Embedding distance 不能识别「真新」vs「已 retract」 | v1.1 接入 OpenAlex retracted DOI 列表，filter 阶段剔除引用 retract 文献的 candidate |
| KG 路径稀疏 Library 上 verifiability 都 < 0.2 | 设 floor `verifiability = max(raw, 0.2)` 兜底；低于 floor 时 UI 标 `(sparse KG)` |
| 公式 0.8/0.2 经验系数过拟合首批校准样本 | §5 月度校准触发参数调整；调整必须配 ADR amendment（不静默改） |
| candidate 与 reference 来自同一篇论文 → novelty 偏低 | reference set 排除 candidate 的来源 doc_id（path.nodes.source_doc_id 反查） |
| LLM 生成的 candidate text 表述虚浮 → embedding 距离虚高 | 生成 prompt 强约束「具体到 method / dataset 名」（在 hypothesize task prompt 里已有，本 ADR 不重复） |
| 月度校准 inter-judge kappa < 0.4 | 不调整参数 — kappa 太低说明判官分歧大，公式没有可优化的「真值」目标 |

### Trade-offs

**为什么 v1 不做 KG embedding（如 TransE / RotatE）算 novelty**：

- KG embedding 训练慢（per-Library 重训，与社区 rebuild 同频，工程量大）
- 文本 embedding 已能拉开 10× novelty 分数差距，性价比足够
- PRD §15.2 v2 候选已列入「图嵌入 + 链接预测」，本 ADR 留接口不实现

**为什么 v1 不做 引用计数反向（PRD §12.2 提到）作为 novelty 的第二成分**：

- 引用数据来自 OpenAlex / Semantic Scholar，外部 API 依赖（与 R07 硬件
  瓶颈风险关联）
- 与文本 distance 相关性高（被引多 = 已知 = 距离近），新增维度边际信息少
- v1.1 重新评估

**为什么 sort_key 不带 verifiability**：见 §2 表格 — 第二行（高 novelty +
高 confidence + 低 verifiability）值得展示，verifiability 应当作 「filter
后的辅助维度」 而非 「排序权重」。

## Alternatives Considered

| 方案 | 拒绝原因 |
|---|---|
| LLM-as-judge 直接打 1-5 分 | 每条假设 1 次 LLM 调用 × 15 条 = 任务成本翻倍，与 R01 冲突 |
| 三维等权加和 sort=N+C+V | 「老调重弹但可验证」会刷屏（V 单维拉分）；与 PRD §12.5 不一致 |
| 三维等权乘 sort=N×C×V | 略掉 §2 第二行（高 novelty + 高 conf + 低 verif）— 低估哲学性假设 |
| 用 Bayesian 后验 | 需要先验数据，冷启动 200 条远不够；解释性差 |
| Confidence = 算术均值 | 弱证据被高分稀释，不符合「最弱链路决定」直觉 |
| Filter 阈值 `len(paths) ≥ 1` | 单路径假设证据链脆，不满足 PRD §12.5「至少 2 条」要求 |
| Novelty 全 web baseline（OpenAlex） | 跨领域 embedding 不可比；外部 API 依赖；隐私风险 |
| 前端纯展示，后端不存 sort_key | 列表分页要 ORDER BY；存 sort_key denormalized，避免 N+1 |

## Open Questions

1. **v1.1 是否引入 retract 信号** — 需要选 OpenAlex / Retraction Watch / Crossref
   作为 retract 数据源；ADR-0020-amendment 时再决定。
2. **KG embedding 替换文本 embedding** — PRD §15.2 v2 候选；M9+ 评估。
3. **多 judge 校准的 inter-judge kappa < 0.4 时怎么办** — 当前决定「不调参
   数」，但是否应当转用 LLM-judge 作为 ground truth？保留为未决。
4. **cross-Library hypothesis** — v1 不做（与 ADR-0003 一致），v2 是否允许「同
   一 entity pair 在 A 库 vs B 库的 novelty 对比」？需要解决 embedding
   不可比性。
5. **baseline 大小的最优值** — 200 是工程拍脑袋；可在 §5 校准期间扫 50/100/
   200/500 看 Spearman ρ 变化。

## 与其他 ADR 的关系

- **ADR-0003 Library as data partition**：novelty baseline 严格 per-Library，
  与 §16.6 数据隔离纪律一致；不存在跨 Library reference set。
- **ADR-0006 Local vs Global routing**：hypothesize 任务走 global 路径（社区
  摘要驱动），baseline 复用 community summary embedding，没有新存储。
- **ADR-0008 Context Management**：embedding 缓存机制可复用 — context 模块
  对 query 的 embedding 缓存与本 ADR 的 baseline cache 是同一基础设施。
- **ADR-0015 Daily Cost Cap**：评分本身零 LLM 成本；月度 LLM-judge 对照走
  cost gateway 与其他任务一致受 cap 控制。
- **ADR-0016 VAR**：hypothesis 任务的 VAR 计算依赖本 ADR 的 sort_key 排序
  — 用户「采纳/拒绝」反馈累积到 VAR 时，需要按 sort_key 分桶看公式有没
  有过拟合。
- **ADR-0021 Eval Alerts**：本 ADR 的「Spearman ρ ≥ 0.6」可作为月度 alert
  规则候选（ρ 跌破 0.5 → 告警），但当前不在 §3.8 Gap 2 alert rule 列表
  内（保留为 v1.1）。

## References

- PRD §12.2 D5.3 验收（5 实体对 × 3 假设 × 三维评分）
- PRD §12.5 风险「假设合理但无据」（filter 边界来源）
- PRD §13.2 LLM-as-Judge（校准方法的渊源）
- PRD §15.2 v2 候选（图嵌入演进路径）
- PRD §16.6 Library 维度纪律（baseline per-Library 来源）
- PRD §17 R01 LLM 成本失控（拒绝 LLM-judge 主路径的依据）
- BACKEND_ROADMAP §3.7 Gap 2（实现位置定义）
- BACKEND_ROADMAP §6.2 P2 排期 行 903（v1.1 滑动空间）
- BACKEND_ROADMAP §7 BR04（VAR 反馈样本少导致指标抖动 — 同源问题）
- `packages/orchestration/tasks/hypothesis.py`（待实现）
- `packages/orchestration/cache/novelty_baseline.py`（新）
- `packages/core/models.py` — `HypothesisCandidate`, `ScoreVector`
- `data/state/hypothesis_cache.sqlite`（新）
- `data/calibration/hypothesis/<yyyy-mm>.json`（月度校准结果）
