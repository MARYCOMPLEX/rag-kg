# 评测子系统架构与集成方案

**模块**：`packages/evaluation/`
**文档状态**：v0.1 / Draft
**最后更新**：2026-04-26
**配套文档**：[`../CODING_STANDARDS.md`](../CODING_STANDARDS.md) · [`../PRD.md`](../PRD.md)

> 本文是**评测子系统的技术规范与集成蓝图**。回答三个问题：评测**做什么**、评测**怎么做**、评测**如何与现有 L1–L5 系统交互而不破坏架构**。

---

## 目录

1. [设计原则](#1-设计原则)
2. [整体架构](#2-整体架构)
3. [三种执行模式](#3-三种执行模式)
4. [组件详解](#4-组件详解)
5. [与现有系统的交互边界](#5-与现有系统的交互边界)
6. [数据模型与 Postgres Schema](#6-数据模型与-postgres-schema)
7. [CLI 设计](#7-cli-设计)
8. [CI/CD 集成](#8-cicd-集成)
9. [按层评测路径](#9-按层评测路径)
10. [隔离性与防污染](#10-隔离性与防污染)
11. [成本与速度优化](#11-成本与速度优化)
12. [按里程碑实施](#12-按里程碑实施)
13. [Anti-Patterns（绝对不要做）](#13-anti-patterns绝对不要做)
14. [附录 A — Alembic 迁移草稿](#附录-a--alembic-迁移草稿)
15. [附录 B — Typer CLI 骨架](#附录-b--typer-cli-骨架)
16. [附录 C — 评测样本 YAML 模板](#附录-c--评测样本-yaml-模板)

---

## 1. 设计原则

| # | 原则 | 含义 |
|---|------|------|
| P1 | **走正门** | Eval 作为正常客户端调用 L5 接口；不开后门、不绕架构、不为 eval 写 fast path |
| P2 | **数据隔离** | 用 `library_id = "_eval_*"` 物理隔离；生产 Library 永远只读 |
| P3 | **模型隔离** | LLM-Judge **必须**与生成模型不同（防自欺） |
| P4 | **成本可见** | 每个 sample 的 token / $ 显式计算并入库 |
| P5 | **可追溯** | 每个 sample 输出有 trace_id（Langfuse）+ artifact（MinIO） |
| P6 | **可重放** | Replay mode 用历史 trace 复跑生成阶段，零边际成本回归 prompt |
| P7 | **不污染依赖** | `evaluation` 是 terminal package —— 没有任何包 import 它 |
| P8 | **Library 维度感知** | 评测集 per-Library 组织；指标按 Library 切分 |

---

## 2. 整体架构

```
┌───────────────────────────────────────────────────────────────────┐
│              packages/evaluation/  (L5 同层，但只调用不被调用)     │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ① Sample Loader                                                   │
│     tests/evals/<lib>/qa.smoke.v1.yaml ─→ EvalSample (Pydantic)    │
│                            │                                       │
│                            ▼                                       │
│  ② Run Planner ─→ 决定 mode (live / sandbox / replay)              │
│                            │                                       │
│                            ▼                                       │
│  ③ Executor ──────调────►  L5 Orchestration (QATask/ReviewTask)   │
│                            │       │                              │
│                            │       └─→ L4 retrieval ─→ L3 ─→ L2  │
│                            ▼                                       │
│                     AnsweredQuery + RetrievalTrace                 │
│                            │                                       │
│                            ▼                                       │
│  ④ Metric Computer                                                 │
│     ├─ Deterministic   (Recall@k / Citation F1 / latency)          │
│     ├─ Ragas           (Faithfulness / Answer Rel / Ctx P&R)       │
│     └─ LLM-Judge        (G-Eval, 用 *另一个* 模型)                 │
│                            │                                       │
│                            ▼                                       │
│  ⑤ Result Store                                                    │
│     ├─ Postgres: eval_runs / eval_results / eval_samples           │
│     ├─ MinIO:    answer.txt / trace.json / context_dump.jsonl      │
│     └─ Langfuse: tag = eval_run_<id>                               │
│                            │                                       │
│                            ▼                                       │
│  ⑥ Reporter                                                        │
│     ├─ Markdown table  → PR comment (CI)                           │
│     ├─ Prometheus push → Grafana                                   │
│     └─ Diff vs baseline → 阻塞 / 告警                              │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
                                ↓
                     依赖方向（Tach 受控）
                                ↓
        evaluation → orchestration → retrieval → indexing → core
        evaluation → llm   (Judge LLM 独立通道)
        evaluation → core  (models / config)
        evaluation NEVER ← anything (无人 import 它)
```

**关键约束**：
- `evaluation` 是 **terminal package**：CLI / CI 是仅有的入口。
- 调用 L5 接口与正常用户**字节级一致**，确保评测的就是真实路径。
- Sandbox / Replay 通过**独立 Library** 与 **trace 缓存**实现，不需要在被测代码里加任何 `if eval:` 分支。

---

## 3. 三种执行模式

### 3.1 Mode A — Live（生产保真）

**何时**：发布前、月度审计、人工抽查。
**机制**：对真实 Library 跑全套（建议是该 Library 的克隆 `_eval_clone_<lib>`），真调用 LLM、真查向量库、真走 Agent。
**代价**：贵 + 慢。
**收益**：最真实。

### 3.2 Mode B — Sandbox（默认）

**何时**：每天 nightly、PR 阻塞、回归测试。
**机制**：从**固定黄金语料**重建一个临时 Library `_eval_<suite>_<runid>`，跑完即销毁。
**代价**：每次 5–10 分钟（首次；缓存命中后秒级）。
**收益**：状态干净；可重复；不污染。

### 3.3 Mode C — Replay（成本敏感）

**何时**：改 prompt / LLM 路由 / 生成参数，**不**改检索逻辑时。
**机制**：从 Langfuse 拉过去某次 run 的 `(query, retrieved_chunks, llm_input)`，复用检索结果，只重跑生成 + 评分。
**代价**：极低（几乎无 LLM 调用）。
**收益**：分钟级 + 可比性极强。

### 3.4 决策树

```
改了什么？
├─ 数据层 (Qdrant/Neo4j adapter)        → Mode B
├─ 检索 / Agent 策略                    → Mode B
├─ Prompt / LLM 路由                    → Mode C → 周末 Mode B 复核
├─ Embedder / Reranker                   → Mode B 全跑
├─ 解析 / Chunking                       → Mode B + 必须重灌
├─ 仅 UI / API 路由                      → 跳过 eval
└─ 准备发版                              → Mode A 全套
```

---

## 4. 组件详解

### 4.1 Sample Loader

评测集位于 `data/libraries/<library_id>/evals/`，与 Library 语料同目录管理。

```python
# packages/evaluation/loader.py
class EvalSample(BaseModel):
    sample_id: str
    library_id: str                       # 评测集所属（生产 lib id）
    suite: str                            # "qa.smoke" / "review.v1"
    suite_version: str
    question: str | None
    inputs: dict[str, object]             # 任务特化输入（review topic 等）
    expected_evidence_doc_ids: list[str]
    expected_key_points: list[str]
    must_not_contain: list[str] = []
    difficulty: Literal["easy", "medium", "hard"]
    type: Literal["single-hop", "multi-hop", "global", "definition"]
    acceptable_score_floor: float = 0.7
    human_validated: bool = False

class SampleLoader(Protocol):
    def load_suite(
        self, library_id: str, suite: str, version: str
    ) -> list[EvalSample]: ...
```

**职责**：YAML → 校验 schema → 校验 doc_id 真实存在于该 Library → 返回类型化样本流。

### 4.2 Run Planner

```python
class RunPlan(BaseModel):
    run_id: UUID
    suite: str
    library_id: str                       # 实际跑的 Library（可能是 _eval_*）
    source_library: str                   # 评测集所属（生产 lib id）
    mode: Literal["live", "sandbox", "replay"]
    system_version: str                   # git SHA + image tag
    judge_model: str                      # 与生成模型不同
    parallelism: int = 4
    sample_ids: list[str]
    baseline_run_id: UUID | None
```

### 4.3 Executor

```python
class EvalExecutor:
    def __init__(
        self,
        qa_task: QATask,                  # DI 注入正常 task
        review_task: ReviewTask,
        sandbox: SandboxManager | None,
        replay: ReplayClient | None,
    ) -> None: ...

    async def execute(
        self, sample: EvalSample, mode: str
    ) -> ExecutedSample:
        match mode:
            case "live" | "sandbox":
                result = await self._qa_task.answer(
                    library_id=sample.library_id,
                    question=sample.question,
                )
            case "replay":
                result = await self._replay.replay(sample.sample_id)
        return ExecutedSample(sample=sample, result=result)
```

### 4.4 Sandbox Manager

```python
class SandboxManager:
    """临时 Library 的生命周期管理。"""

    async def acquire(self, suite: str, corpus_path: Path) -> str:
        lib_id = f"_eval_{suite}_{uuid7()}"
        await library_admin.init(lib_id)
        await self._ingestion.batch_ingest(lib_id, corpus_path)
        await self._indexing.rebuild_all(lib_id)
        return lib_id

    async def release(self, library_id: str) -> None:
        await library_admin.purge(library_id)
```

**优化**：
- **指纹缓存**：`hash(corpus_path)` 不变时复用上次 ephemeral Library
- **共享只读 Library**：纯查询型 suite 共用 `_eval_shared_<corpus_hash>`

### 4.5 Metric Computer

```python
class Metric(Protocol):
    name: str
    requires_judge: bool
    requires_ground_truth: bool

    async def score(
        self, sample: EvalSample, result: AnsweredQuery
    ) -> MetricScore: ...

class MetricScore(BaseModel):
    metric_name: str
    score: float                          # 0..1
    details: dict[str, object]
    judge_model: str | None
    cost_usd: float = 0.0
    error: str | None = None
```

**指标矩阵**：

| Metric | 实现 | 依赖 |
|--------|------|------|
| `RecallAtK` | retrieved doc_ids ∩ expected | 无 LLM |
| `CitationF1` | 抽 claim → 验 cite chunk 含支持文本 | 轻量 LLM-Judge |
| `Faithfulness` | Ragas 实现 | LLM-Judge |
| `AnswerRelevancy` | Ragas | LLM-Judge |
| `KeyPointCoverage` | 判 expected_key_points 命中数 | LLM-Judge |
| `MustNotContain` | 字符串/正则匹配 | 无 LLM |
| `Latency` | result.duration_ms | 无 LLM |
| `Cost` | 累加 token usage | 无 LLM |

**并发**：每 sample 的所有 metric 用 `asyncio.TaskGroup` 并发；同 sample 的多个 LLM-Judge 调用共享 rate limit。

### 4.6 LLM-Judge 防自欺

```python
class JudgeRouter:
    """强制 Judge 与生成走不同模型族。"""

    def select_judge(self, generator_model: str) -> str:
        match generator_model:
            case s if "claude" in s: return "qwen2.5-72b"
            case s if "gpt" in s:    return "claude-sonnet-4-6"
            case s if "qwen" in s:   return "claude-haiku-4-5"
            case _:                  raise ValueError(f"no judge for {generator_model}")
```

**人工校准**：每月抽 30 sample 让人审，与 Judge 比对。一致率 < 0.85 → 触发 Judge prompt 重调 + 写 ADR。

### 4.7 Reporter

三路输出：

1. **Markdown table → PR comment**
2. **Prometheus push → Grafana**
3. **Gate decision**（baseline diff，阻塞合并或告警）

---

## 5. 与现有系统的交互边界

### 5.1 唯一调用路径

```
┌────────────────────────┐
│  evaluation.runner     │  ← CLI/CI 入口
└──────────┬─────────────┘
           │ DI 注入 QATask / ReviewTask / SandboxManager
           ▼
┌────────────────────────┐
│  orchestration.qa_task │  ← 完全不知道自己被 eval
└──────────┬─────────────┘
           │ 标准 Protocol
           ▼
┌────────────────────────┐
│  retrieval.planner     │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│  indexing / structuring│
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│  llm.gateway           │  ← Judge LLM 也走它，但用不同 model
└────────────────────────┘
```

### 5.2 一次 sample 的完整旅程

```
1. CI 触发 ──→ make eval-pr
2. 加载 EvalSample（YAML）
3. RunPlanner 决定 mode=sandbox
4. SandboxManager.acquire() → 创建 _eval_smoke_xyz Library
5. Ingestion 灌固定语料（缓存命中→跳过）
6. Indexing 重建（缓存命中→跳过）
7. Executor.execute(sample) → QATask.answer(_eval_smoke_xyz, question)
   ├─ Trace 写 Langfuse, tag=eval_run_xyz
   └─ 返回 AnsweredQuery
8. MetricComputer 并发计算 6 个指标
   ├─ RecallAtK     (本地)
   ├─ CitationF1    (Judge LLM)
   ├─ Faithfulness  (Ragas + Judge LLM)
   ├─ AnswerRel     (Ragas + Judge LLM)
   ├─ KeyPointCov   (Judge LLM)
   └─ Latency/Cost  (本地)
9. 写 eval_results 表 + 上传 artifact 到 MinIO
10. Reporter 生成 markdown → 贴 PR
11. SandboxManager.release() → purge _eval_smoke_xyz
```

### 5.3 可交互资源清单

| 资源 | 用途 | 隔离方式 |
|------|------|---------|
| Postgres | 存 eval_runs / eval_results | 独立 schema `eval` |
| MinIO | 存 artifact | bucket prefix `kb-eval/<run_id>/` |
| Langfuse | LLM trace 全量 | tag `eval_run_<id>`；可单独项目 |
| Qdrant / Neo4j / OpenSearch | sandbox Library 的物理分区 | collection/db/index 名前缀 `_eval_` |
| LLM Gateway | 生成 + Judge 调用 | Gateway 维护 `eval_budget` 独立 token bucket |

---

## 6. 数据模型与 Postgres Schema

### 6.1 领域模型

```python
# packages/evaluation/models.py
class EvalRun(BaseModel):
    run_id: UUID
    suite: str
    suite_version: str
    library_id: str                       # 实际跑的 lib（可能 _eval_*）
    source_library: str                   # 评测集所属
    system_version: str                   # git SHA
    mode: Literal["live", "sandbox", "replay"]
    started_at: datetime
    finished_at: datetime | None = None
    total: int
    passed: int = 0
    failed: int = 0
    config: dict[str, object] = Field(default_factory=dict)

class EvalResult(BaseModel):
    run_id: UUID
    sample_id: str
    metric: str
    score: float | None
    passed: bool
    details: dict[str, object] = Field(default_factory=dict)
    trace_id: str | None = None
    artifact_uri: str | None = None
    judge_model: str | None = None
    cost_usd: float = 0.0
```

### 6.2 Schema（具体 SQL 见 [附录 A](#附录-a--alembic-迁移草稿)）

`eval_runs` / `eval_results` 两张主表 + 索引。所有数据放独立 schema `eval`，与生产数据彻底分隔。

---

## 7. CLI 设计

```bash
# 跑评测（默认 sandbox）
rkb eval run \
  --suite qa.smoke \
  --library graphrag \
  --judge claude-sonnet-4-6

# 列最近的 run
rkb eval list --recent 10

# 看一个 run 的详情
rkb eval show <run_id>

# 与 baseline 对比
rkb eval diff --from v0.5.0 --to HEAD --suite qa.smoke

# 重放某次 run（cached LLM，便宜验证 prompt 改动）
rkb eval replay <run_id> --new-prompt path/to/v2.jinja

# 单 sample 调试（不写 DB，只输出 markdown）
rkb eval debug --sample qa-014 --library graphrag --verbose

# CI Gate
rkb eval gate \
  --run-id <id> \
  --baseline main \
  --max-regression 0.05 \
  --fail-on var,citation_f1
```

完整 Typer 骨架见 [附录 B](#附录-b--typer-cli-骨架)。

---

## 8. CI/CD 集成

### 8.1 PR 阻塞工作流

```yaml
# .github/workflows/eval-on-pr.yml
name: Eval Gate
on: pull_request

jobs:
  eval-smoke:
    runs-on: gpu-runner
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f infra/docker-compose.yml up -d
      - run: uv sync --frozen

      - name: Restore eval Library cache
        uses: actions/cache@v4
        with:
          path: data/sandbox/_eval_smoke
          key: eval-smoke-${{ hashFiles('tests/evals/corpus/smoke/**') }}

      - name: Run smoke eval
        env:
          LLM_KEY: ${{ secrets.LLM_KEY }}        # 生成
          JUDGE_KEY: ${{ secrets.JUDGE_KEY }}    # Judge（不同厂商）
        run: rkb eval run --suite qa.smoke --library graphrag

      - name: Gate
        run: rkb eval gate --baseline main --max-regression 0.05

      - name: Comment PR
        if: always()
        run: rkb eval report --format pr-comment --post
```

### 8.2 阻塞规则

| 检测 | 阈值 | 动作 |
|------|------|------|
| 任一指标对 baseline 退步 | > 5 pp | 阻塞 |
| P95 延迟退步 | > 20% | 阻塞 |
| 成本退步 | > 30% | 阻塞 |
| 单个 sample 失败 | > 30% 总数 | 阻塞 |
| Judge 不可用（API 失败） | — | 降级到 deterministic-only，告警不阻塞 |

### 8.3 节奏

| 频率 | 跑什么 | 阻塞 |
|------|------|------|
| Pre-commit | ruff / pyright / unit | 是 |
| PR | unit + integration + smoke eval | 是 |
| Merge | smoke + perf benchmark | 是 |
| Nightly | multihop + reasoning + 性能基线 | 通知 |
| Weekly | review + adversarial + 全 Library | 通知 |
| Pre-release | 全套 + 人工抽查 + drill backup | 是 |
| Monthly | 评测集扩充 + Judge 校准 | — |

---

## 9. 按层评测路径

| 层 | 评测调用方式 | 独立可测 |
|---|--------------|---------|
| **L1 摄取** | 调 `Parser.parse()` / `Chunker.chunk()`，对比固定 PDF 的预期输出 | ✅ 纯单元 |
| **L2 KG** | 调 `EntityExtractor.extract()` / `RelationExtractor.extract()`，对比 triple 金牌集 | ✅ sandbox Library |
| **L3 Index** | 灌入固定 chunks → 调 `VectorIndex.search()` / `GraphIndex.expand()`，对比 expected_evidence | ✅ sandbox |
| **L4 Agent** | 调 `RetrievalPlanner.plan_and_retrieve()`，看 trace 步数与最终 evidence | ✅ sandbox |
| **L5 Task** | 调 `QATask.answer()` / `ReviewTask.run()`，端到端 | ✅ sandbox / live |

**问题归因路径**（VAR 退步时按此向下找）：
```
VAR 退步
  ↓
L5 端到端 score 退步
  ↓
L4 trace 显示 evidence 错
  ↓
L3 Recall@10 退步
  ↓
多半是 embedder 改动或索引参数
```

---

## 10. 隔离性与防污染

| 风险 | 防护 |
|------|------|
| Eval 写入污染生产 Library | Sandbox Library 名前缀 `_eval_`；ingestion API 拒绝在生产 lib 上由 eval-tag 触发的写 |
| Eval LLM 调用混入产线统计 | Langfuse 按 `tag=eval_run_*` 分桶；Grafana 默认过滤 |
| Eval 用尽 LLM 配额 | LLM Gateway 维护 `eval_budget` 独立 token bucket |
| Eval 占 GPU 阻塞线上 | 低优先队列；K8s priority class（生产化后） |
| Sandbox Library 残留 | 每天 `cleanup_orphan_eval_libraries` cron 扫 `_eval_*` 超 24h 未释放的 |
| Eval 与生产共享 Postgres 误操作 | 独立 schema `eval`，生产用户角色无写权限 |

---

## 11. 成本与速度优化

| 优化 | 效果 |
|------|------|
| Sandbox 语料指纹缓存 | 同语料不重新 ingest（90% 时间省） |
| Replay mode 缓存 LLM 调用 | Prompt 改动评测 ≤ 1 分钟 |
| 金牌集分层（smoke / full） | smoke 每 PR 跑（< 5min）；full nightly |
| 并发 sample 执行 | 30 题 × 5 并发 → 总时长缩 5× |
| Judge 走小模型（Haiku） | 单 sample 评测成本 ≤ $0.01 |
| 指标计算并发 | 6 指标并行算 |
| Fail-fast | smoke 致命指标 < 阈值立刻 abort |

---

## 11.5 评测集自动生成

评测集与 Library 同目录管理（`data/libraries/<library_id>/evals/`）。支持从已灌入语料自动生成。

### 自动生成流程

```
rkb eval generate --library <id> --suite qa.smoke --count 10
```

1. 从 Library 的 chunk 中采样 N 个高质量片段（优先选长度适中、含实体多的 chunk）
2. LLM 基于每个 chunk 生成 `(question, expected_key_points, difficulty, type)` 四元组
3. 自动填充 `expected_evidence_doc_ids`（来源 chunk 所属文档）
4. 输出 YAML 到 `data/libraries/<id>/evals/qa.smoke.v1.yaml`
5. 所有自动生成的 sample 标记 `human_validated: false`、`created_by: "auto"`

### 人工审核

```
rkb eval review --library <id> --suite qa.smoke
```

逐条展示 auto-generated sample，用户确认/修改/删除后标记 `human_validated: true`。

### 质量约束

- CI gate 只使用 `human_validated: true` 的 sample
- Nightly 可跑全集（含 auto-generated 未审核的）
- 至少 50% sample 需人工审核后才能用作 PR 阻塞门槛

### Prompt 原则

- 生成 prompt 与被测 QA prompt **完全隔离**（防评测泄露）
- 生成用的 LLM 应与 Judge LLM **不同**（防自欺）
- 生成 prompt 模板纳入版本控制：`packages/evaluation/prompts/generate_qa.jinja`

---

## 12. 按里程碑实施

| 里程碑 | 评测子系统建什么 | 依赖 |
|-------|-----------------|------|
| **M0** | `packages/evaluation/protocols.py` 占位（Protocol + 模型） | — |
| **M1** | Sample Loader + 最简 Executor + RecallAtK + Latency；只支持 sandbox | M1 有 QATask |
| **M2** | + CitationF1 + KG triple 金牌集对比 | M2 有 KG |
| **M3** | + Community 摘要 coverage 测量 | M3 有 community |
| **M4** | + RetrievalTrace 分析；引入 Replay mode 雏形 | M4 有 Langfuse |
| **M5** | + Review/Hypothesis 任务级评测（人工 + LLM-Judge） | M5 有任务 |
| **M6** | **完整 Result Store + Grafana + PR Gate + Alerting**（成熟点） | M6 把所有连起 |
| **M7** | 备份/恢复 drill 自动化；α 用户反馈采集闭环 | M7 有 UI |
| **M8** | 持续 perf benchmark；评测集季度审计；Judge 校准 | — |

---

## 13. Anti-Patterns（绝对不要做）

| 反模式 | 为什么不行 |
|--------|----------|
| 给 evaluation 开个绕过 L4 的"快通道" | 破坏架构合规；评测的就不是真实系统 |
| Eval 直接 SQL 改生产 Library | 污染数据；非幂等 |
| 同一 LLM 既生成又评判 | 自欺；G-Eval 论文证误差大 |
| 金牌集与生成 prompt 共享 few-shot | 评测泄露；指标虚高 |
| 指标取平均不分桶 | 隐藏多跳问题退步 |
| 失败 sample 不存 artifact | 无法事后归因 |
| Eval 在生产 Postgres 写百万行 | 用单独 schema 或单独 DB |
| 跨 Library 联合评测 | 与系统能力不一致；先建立单 Library 基线 |
| 给 evaluation 加新的领域模型 | evaluation 只读 / 编排，不创造新概念 |

---

## 附录 A — Alembic 迁移草稿

新建 `infra/migrations/versions/0002_evaluation_schema.py`：

```python
"""create eval schema and tables

Revision ID: 0002_evaluation_schema
Revises:     0001_initial
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_evaluation_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 独立 schema 与生产数据隔离
    op.execute("CREATE SCHEMA IF NOT EXISTS eval")

    op.create_table(
        "eval_runs",
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite", sa.Text, nullable=False),
        sa.Column("suite_version", sa.Text, nullable=False),
        sa.Column("library_id", sa.Text, nullable=False),
        sa.Column("source_library", sa.Text, nullable=True),
        sa.Column("system_version", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("passed", sa.Integer, nullable=True),
        sa.Column("failed", sa.Integer, nullable=True),
        sa.Column("config", sa.dialects.postgresql.JSONB, nullable=True),
        sa.CheckConstraint("mode IN ('live', 'sandbox', 'replay')", name="ck_mode"),
        schema="eval",
    )
    op.create_index(
        "ix_eval_runs_suite_sysver",
        "eval_runs",
        ["suite", "system_version"],
        schema="eval",
    )
    op.create_index(
        "ix_eval_runs_library",
        "eval_runs",
        ["source_library"],
        schema="eval",
    )

    op.create_table(
        "eval_results",
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval.eval_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sample_id", sa.Text, nullable=False),
        sa.Column("metric", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("details", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("trace_id", sa.Text, nullable=True),
        sa.Column("artifact_uri", sa.Text, nullable=True),
        sa.Column("judge_model", sa.Text, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.PrimaryKeyConstraint("run_id", "sample_id", "metric"),
        schema="eval",
    )
    op.create_index(
        "ix_eval_results_sample_metric",
        "eval_results",
        ["sample_id", "metric"],
        schema="eval",
    )

    # 评测集元信息（YAML 版本登记，便于追溯哪份 run 用了哪份评测集）
    op.create_table(
        "eval_suites",
        sa.Column("suite", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("library_id", sa.Text, nullable=False),
        sa.Column("sample_count", sa.Integer, nullable=False),
        sa.Column("checksum", sa.Text, nullable=False),       # YAML hash
        sa.Column("registered_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("suite", "version", "library_id"),
        schema="eval",
    )


def downgrade() -> None:
    op.drop_table("eval_suites", schema="eval")
    op.drop_table("eval_results", schema="eval")
    op.drop_table("eval_runs", schema="eval")
    op.execute("DROP SCHEMA IF EXISTS eval CASCADE")
```

**注**：依赖一个 `0001_initial` 迁移（M0/M1 时建 `Library` 等基础表）。当前为占位 ID，等 M0 落地后改成真实 revision。

---

## 附录 B — Typer CLI 骨架

新建 `apps/cli/eval.py`（被 `apps/cli/main.py` 中的 `app.add_typer(eval_app, name="eval")` 挂载）：

```python
"""rkb eval — evaluation subsystem CLI."""
from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from apps.cli.deps import build_eval_runner, build_eval_reporter, build_eval_store

app = typer.Typer(help="评测子系统：跑评测、看结果、对比 baseline、CI gate。")
console = Console()


@app.command()
def run(
    suite: str = typer.Option(..., help="评测集名，如 qa.smoke"),
    library: str = typer.Option(..., "--library", "-l", help="评测集所属生产 Library"),
    mode: str = typer.Option("sandbox", help="live / sandbox / replay"),
    judge: str | None = typer.Option(None, help="Judge 模型；省略时由 JudgeRouter 决定"),
    parallelism: int = typer.Option(4, help="并发 sample 数"),
    baseline: str | None = typer.Option(None, help="对比的 baseline run_id 或 git ref"),
) -> None:
    """跑一次评测。"""
    runner = build_eval_runner()
    plan = runner.plan(
        suite=suite,
        library_id=library,
        mode=mode,
        judge_model=judge,
        parallelism=parallelism,
        baseline=baseline,
    )
    console.print(f"[green]Run plan:[/green] {plan.run_id}  mode={mode}  samples={len(plan.sample_ids)}")
    summary = asyncio.run(runner.execute(plan))
    console.print(
        f"[bold]Done:[/bold] passed={summary.passed}/{summary.total}  "
        f"avg_var={summary.avg_var:.3f}  cost=${summary.total_cost_usd:.2f}"
    )


@app.command("list")
def list_runs(recent: int = typer.Option(10, help="显示最近 N 个 run")) -> None:
    """列最近的评测 run。"""
    store = build_eval_store()
    runs = asyncio.run(store.list_recent(recent))
    table = Table(title=f"Recent {len(runs)} eval runs")
    for col in ["run_id", "suite", "library", "mode", "passed/total", "started"]:
        table.add_column(col)
    for r in runs:
        table.add_row(
            str(r.run_id)[:8],
            f"{r.suite}@{r.suite_version}",
            r.source_library,
            r.mode,
            f"{r.passed}/{r.total}",
            r.started_at.isoformat(timespec="minutes"),
        )
    console.print(table)


@app.command()
def show(run_id: UUID) -> None:
    """看一个 run 的详细结果（per-sample / per-metric）。"""
    store = build_eval_store()
    run = asyncio.run(store.get_run(run_id))
    results = asyncio.run(store.list_results(run_id))
    console.print(f"[bold]Run[/bold] {run_id}  suite={run.suite}@{run.suite_version}")
    table = Table()
    for col in ["sample", "metric", "score", "passed", "judge", "cost"]:
        table.add_column(col)
    for r in results:
        table.add_row(
            r.sample_id,
            r.metric,
            f"{r.score:.3f}" if r.score is not None else "-",
            "✓" if r.passed else "✗",
            r.judge_model or "-",
            f"${r.cost_usd:.4f}",
        )
    console.print(table)


@app.command()
def diff(
    from_: str = typer.Option(..., "--from", help="baseline run_id 或 git ref（如 v0.4.2）"),
    to: str = typer.Option("HEAD", help="对比的目标 run"),
    suite: str = typer.Option(..., help="suite 名"),
) -> None:
    """两次 run 的指标对比，输出 markdown 表。"""
    reporter = build_eval_reporter()
    md = asyncio.run(reporter.diff(from_=from_, to=to, suite=suite))
    console.print(md)


@app.command()
def replay(
    run_id: UUID,
    new_prompt: Path = typer.Option(..., exists=True, dir_okay=False),
) -> None:
    """重放某次 run，但用新的 prompt 模板（验证 prompt 改动）。"""
    runner = build_eval_runner()
    summary = asyncio.run(runner.replay(run_id, new_prompt=new_prompt))
    console.print(
        f"[green]Replay done[/green] passed={summary.passed}/{summary.total}  "
        f"cost=${summary.total_cost_usd:.2f}"
    )


@app.command()
def debug(
    sample: str = typer.Option(..., help="sample_id"),
    library: str = typer.Option(..., "--library", "-l"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """单 sample 调试模式：不写 DB，直接 stdout 输出 trace + 评分明细。"""
    runner = build_eval_runner()
    out = asyncio.run(runner.debug_one(sample_id=sample, library_id=library, verbose=verbose))
    console.print(out)


@app.command()
def gate(
    run_id: UUID = typer.Option(..., help="本次 run"),
    baseline: str = typer.Option("main", help="baseline 标识（git ref / run_id）"),
    max_regression: float = typer.Option(0.05, help="允许的最大退步（pp）"),
    fail_on: list[str] = typer.Option(["var", "citation_f1"], help="哪些指标退步即阻塞"),
) -> None:
    """CI Gate：与 baseline 对比，超阈值退出码非 0（阻塞合并）。"""
    reporter = build_eval_reporter()
    decision = asyncio.run(
        reporter.gate(
            run_id=run_id,
            baseline=baseline,
            max_regression=max_regression,
            fail_on=fail_on,
        )
    )
    if decision.blocked:
        console.print(f"[red]BLOCKED:[/red] {decision.reason}")
        raise typer.Exit(code=1)
    console.print(f"[green]PASS:[/green] {decision.summary}")


@app.command()
def report(
    run_id: UUID = typer.Option(..., help="run_id"),
    format: str = typer.Option("markdown", help="markdown / json / pr-comment"),
    post: bool = typer.Option(False, "--post", help="发布到 PR（需 GH_TOKEN）"),
) -> None:
    """生成报告。"""
    reporter = build_eval_reporter()
    out = asyncio.run(reporter.render(run_id=run_id, format=format, post=post))
    if not post:
        console.print(out)
```

---

## 附录 C — 评测样本 YAML 模板

`data/libraries/<library_id>/evals/qa.smoke.v1.yaml`：

```yaml
# Schema version
$schema_version: "1"
suite: qa.smoke
suite_version: v1
library_id: graphrag

samples:
  - sample_id: qa-001
    question: "HippoRAG 相比 GraphRAG 的核心改进是什么？"
    difficulty: medium
    type: single-hop
    expected_evidence_doc_ids:
      - "arxiv:2405.14831"
      - "arxiv:2404.16130"
    expected_key_points:
      - "Personalized PageRank"
      - "passage-level graph"
      - "without fine-tuning"
    must_not_contain:
      - "fine-tuned"          # 防错答
    acceptable_score_floor: 0.7
    human_validated: true
    created_by: "user"
    created_at: 2026-04-26

  - sample_id: qa-002
    question: "Self-RAG 引入了哪几种 reflection token？"
    difficulty: easy
    type: single-hop
    expected_evidence_doc_ids:
      - "arxiv:2310.11511"
    expected_key_points:
      - "Retrieve"
      - "ISREL"
      - "ISSUP"
      - "ISUSE"
    acceptable_score_floor: 0.8
    human_validated: true

  # ... 8 more samples to reach 10
```

**校验脚本**（loader 内部跑）：
1. YAML schema 合规
2. `expected_evidence_doc_ids` 在该 Library 的 Document 表中真实存在
3. `must_not_contain` 不与 `expected_key_points` 冲突
4. 至少 50% sample 标 `human_validated: true`

---

## 最后

本文件与 `CODING_STANDARDS.md`、`PRD.md` 形成**项目三支柱**：

| 文档 | 回答 |
|------|------|
| `CODING_STANDARDS.md` | 怎么写代码不后悔 |
| `PRD.md` | 做什么、何时做完 |
| `EVAL_ARCHITECTURE.md` | 怎么知道做对了、退步了没 |

> 评测不是测试的扩展，是产品的另一条命脉。没有评测的 RAG 系统是**信仰系统**，不是工程系统。
