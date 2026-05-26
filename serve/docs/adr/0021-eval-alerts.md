# ADR-0021: Eval 告警规则（VAR / Citation F1 / P95 / Cost）

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M6 D6.3 / M7 S8 — Eval Dashboard 顶部告警 banner；BACKEND_ROADMAP §3.8 Gap 2
**Related**: ADR-0011 (Notification Center), ADR-0013 (Library Status Machine), ADR-0015 (Daily Cost Cap), ADR-0016 (VAR Computation), ADR-0008 (Context Management)
**Supersedes**: none

## Context

PRD §13.2 写明：

> Alerting：VAR 周环比下跌 > 5 pp 告警（按 Library 分别告警）

PRD §14.3 D7.6 / §6 S8 屏要求：

> Eval Dashboard：4 张 KPI 卡（VAR / Citation F1 / P95 / cost）+ 30 天趋势 +
> 失败 case 表 + Library 过滤器 + **VAR 周环比下跌 > 5pp 顶部告警 banner**

`BACKEND_ROADMAP §3.8 Gap 2`（行 724–731）明确点名本 ADR：

> ADR-0021 Eval 告警规则 — 阈值、触发频率、自动恢复条件
> 现状：无
> 文件：`packages/evaluation/alerts.py`（新）：周环比下跌 > 5pp 触发
> 触发后：写 Notification + 写 `alerts` 表（带状态 active/recovered）
> 工作量：S（2 天）

但 PRD 只写死了 1 条规则（VAR -5pp），其他三个 KPI（Citation F1 / P95 / cost）
也需要告警 — 否则 Dashboard 上只有 VAR 一条 banner，其他指标用户得自己点
进趋势图看。`BACKEND_ROADMAP §3.2 Gap 4`（VAR/Citation F1/P95/cost 聚合）
要求 4 维 KPI，告警规则也应当对称覆盖。

仍未决的设计点：

1. **触发频率** — 实时计算太抖、每周一次又错过工作日异常
2. **去重** — 同一规则连续 7 天 active，每天都发通知会刷屏
3. **自动恢复** — 指标回到阈值之上时如何标 recovered，避免 alert 永远 active
4. **小样本噪声** — 评测集 < 30 题时指标抖动剧烈，容易误告警
5. **冷启动** — 第一天部署没有历史，所有「周环比」类规则无法计算
6. **per-Library 还是全局** — 每个 Library 各算还是聚合？
7. **告警通道** — 只写 Notification 还是另有 dashboard endpoint？

PRD §13.5 风险登记已记录「评测集过小导致指标噪音」与「LLM-Judge 不稳定」，
本 ADR 必须回应这两条。BACKEND_ROADMAP §7 BR04（VAR 反馈样本少导致指标
抖动）同源。

## Decision

### 1. 4 条告警规则（v1）

| Rule ID | 指标 | 触发条件 | Severity |
|---|---|---|---|
| `var_weekly_drop` | VAR | 7 天均值环比上周下跌 ≥ 5 pp | danger |
| `citation_f1_weekly_drop` | Citation F1 | 7 天均值环比上周下跌 ≥ 5 pp | warning |
| `p95_latency_weekly_rise` | P95 latency | 7 天 P95 环比上周上升 ≥ 50% | warning |
| `daily_cost_approaching_cap` | Daily cost | 当日累计 ≥ 80% of `LibraryConfig.daily_cost_cap_usd` | warning |
| `daily_cost_exceeded_cap` | Daily cost | 当日累计 ≥ 100% of cap | danger |

最后两条与 ADR-0015 协同 — ADR-0015 已在 LLM Gateway 边写入 `notifications`
表中 `daily_cost_warning` / `daily_cost_blocked` 类型。**本 ADR 把它们也作为
独立的 alert rule 注册到 `alerts` 表**，目的：

- Eval Dashboard 顶部 banner 能统一查 `alerts WHERE status='active'`，
  无需混合查 notifications + 多种指标聚合表
- 跨 Library 视图（如 Library Dashboard）能统一展示「这个 Library 当前有
  几条 active alert」徽章

ADR-0015 的 notifications 写入保持不变；本 ADR 的 alerts 表是另一份**视图**
化的状态记录（见 §3 schema）。

### 2. 触发频率 — 每天 02:30，紧跟 eval_snapshot

```
02:00  apps/worker/jobs/eval_snapshot.py        # ADR 现状（BACKEND_ROADMAP §3.8 Gap 1）
02:30  apps/worker/jobs/eval_alert_evaluator.py # 新（本 ADR）
```

设计要点：

- **每天一次**：日内频率会被单条评测样本噪声放大；每周一次则事故响应慢
- **02:30 跑**：接 02:00 的快照之后；若快照失败，alert evaluator skip 这一天
  并记 log（不告假警）
- **跨 Library 串行评估**：alerts 写入低频，串行简单
- **手动触发**：`rkb eval alerts evaluate --library <id>` 用于测试或事故响应

```python
# apps/worker/jobs/eval_alert_evaluator.py
async def evaluate_all_libraries(now: datetime) -> EvaluationReport:
    libraries = await library_repo.list_active()
    results = []
    for lib in libraries:
        try:
            results.append(await evaluate_library(lib.library_id, now))
        except Exception as e:
            logger.error(f"alert eval failed for {lib.library_id}", exc_info=e)
            results.append(EvaluationFailure(library_id=lib.library_id, error=str(e)))
    return EvaluationReport(now=now, results=results)
```

### 3. `alerts` 表 schema

```sql
CREATE TABLE alerts (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    library_id      TEXT         NOT NULL REFERENCES libraries(library_id) ON DELETE CASCADE,
    rule            TEXT         NOT NULL,         -- 'var_weekly_drop' etc.
    severity        TEXT         NOT NULL CHECK(severity IN ('info','warning','danger')),
    status          TEXT         NOT NULL CHECK(status IN ('active','recovered','expired')),
    triggered_at    TIMESTAMPTZ  NOT NULL,
    recovered_at    TIMESTAMPTZ  NULL,
    recovery_consecutive_days INTEGER NOT NULL DEFAULT 0, -- 见 §4
    payload         JSONB        NOT NULL,         -- {current, previous, delta, sample_size, threshold}
    notification_id UUID         NULL REFERENCES notifications(id), -- 关联 ADR-0011 通知
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX alerts_library_status_idx ON alerts(library_id, status);
CREATE INDEX alerts_rule_status_idx    ON alerts(rule, status);
CREATE UNIQUE INDEX alerts_active_one_per_rule_idx
    ON alerts(library_id, rule)
    WHERE status = 'active';                       -- 同一规则同时只能一条 active
```

`payload` 示例：

```json
{
  "metric": "var",
  "current_value": 0.62,
  "previous_value": 0.71,
  "delta_pp": -9.0,
  "threshold_pp": -5.0,
  "current_window": "2026-05-29..2026-06-04",
  "previous_window": "2026-05-22..2026-05-28",
  "sample_size": 47,
  "min_sample_size_required": 30
}
```

### 4. 自动恢复 — 连续 2 天指标回到阈值上

为什么 2 天而不是 1 天：单日反弹可能是噪声，2 天连续才相对可信。

```python
def evaluate_recovery(active_alert: Alert, today_metric: MetricSample) -> Alert | None:
    if not is_recovered_today(active_alert.rule, today_metric):
        return active_alert.with_recovery_consecutive_days(0)

    new_count = active_alert.recovery_consecutive_days + 1
    if new_count < 2:                              # 还没满 2 天，等明天
        return active_alert.with_recovery_consecutive_days(new_count)

    # 连续 2 天 OK → 标 recovered
    return active_alert.with_status('recovered', recovered_at=today_metric.observed_at)
```

`is_recovered_today` 各 rule 实现：

| Rule | 恢复条件 |
|---|---|
| `var_weekly_drop` | 当前 7 天 VAR ≥ 上一报警基准（trigger 时的 previous_value） − 2pp |
| `citation_f1_weekly_drop` | 同上 |
| `p95_latency_weekly_rise` | 当前 P95 ≤ 上次基准 × 1.2（即只剩 20% 上升） |
| `daily_cost_approaching_cap` | 当日累计 < 70% cap（5pp 滞后避免抖动） |
| `daily_cost_exceeded_cap` | 当日累计 < 90% cap |

恢复时**写 recovered notification**（severity=info），让用户看见「指标回来了」
正反馈。

### 5. 抑制（去重）策略

```python
async def trigger_alert(library_id: str, rule: str, payload: dict) -> Alert:
    existing = await alerts_repo.find_active(library_id, rule)
    if existing:
        # 已 active：刷新 payload（最新 delta），不发新通知
        return await alerts_repo.update_payload(existing.id, payload)
    # 新 trigger：写 alert + 写 notification
    notification = await notification_service.create(
        library_id=library_id,
        type="alert_triggered",
        severity=severity_for(rule),
        title=title_for(rule, payload),
        payload=payload,
    )
    return await alerts_repo.create(
        library_id=library_id,
        rule=rule,
        severity=severity_for(rule),
        status="active",
        triggered_at=now(),
        payload=payload,
        notification_id=notification.id,
    )
```

去重核心：`UNIQUE INDEX alerts(library_id, rule) WHERE status = 'active'` 保证
同 rule 同 library 同时**只能有一条 active**。重复触发只更新 payload，不发新通知。

只在 **状态切换** 时写 notification：
- `(none)        → active`     → `alert_triggered`（severity 跟随规则）
- `active       → recovered`  → `alert_recovered`（severity=info）
- `recovered    → active`     → `alert_re_triggered`（severity 跟随规则）

### 6. per-Library 独立告警，不做全局聚合

每个 Library 各跑一遍 evaluator，**不做跨 Library 聚合告警**。理由：

- PRD §13.2 显式要求「按 Library 分别告警」
- 一个低活跃 Library 的指标异常会被高活跃 Library 平均掉，全局聚合无意义
- per-Library 与 ADR-0003 物理隔离精神一致；告警是数据维度的延伸

「全局视图」交给前端做 — Library Dashboard 的 KPI 总览面板（PRD §6 S2）
查 `GET /v1/alerts?status=active` 拿全部 active alerts，按 Library 分组渲染
徽章。

### 7. Cold start — 14 天观察期

第一天部署时无历史，所有「周环比」类规则都不能触发（previous_window 为空）。
14 天 cold start 期内的策略：

| Day | 行为 |
|---|---|
| 0–6 | 不评估周环比规则（previous_window 至少需 7 天数据）；只跑 cost 类规则 |
| 7–13 | 评估周环比规则但**只 log，不写 alerts 表**；用于观察阈值是否合理 |
| 14+ | 正常告警 |

cold start 期可通过 `LibraryConfig.alert_cold_start_days` 调整（默认 14）。
Library 创建时 `created_at + cold_start_days` 即生效起点。

### 8. 小样本噪声防护 — `sample_size ≥ 30`

评测集小于 30 题时**不告警**，alert payload 标 `not_enough_data`：

```python
MIN_SAMPLE_SIZE = 30

def evaluate_var_weekly_drop(snapshots: list[EvalSnapshot]) -> EvaluationOutcome:
    current = snapshots_in_window(snapshots, days=7)
    previous = snapshots_in_window(snapshots, days=7, offset=7)
    sample_size = sum(s.sample_size for s in current)
    if sample_size < MIN_SAMPLE_SIZE:
        return EvaluationOutcome.skip(
            reason="not_enough_data",
            sample_size=sample_size,
            min_required=MIN_SAMPLE_SIZE,
        )
    delta_pp = (mean(current) - mean(previous)) * 100
    if delta_pp <= -5.0:
        return EvaluationOutcome.trigger(payload=...)
    return EvaluationOutcome.ok()
```

这与 BACKEND_ROADMAP §7 BR04（VAR 反馈样本少导致指标抖动）的缓解方案
一致：「明确告知用户『样本数 < N 时指标仅供参考』」 — 我们直接在告警
路径上不让噪声变成假警。

UI 上 Eval Dashboard 顶部 banner：

```
┌──────────────────────────────────────────────────────────────┐
│ ⚠ VAR dropped 9pp this week (0.62 ← 0.71, sample n=47)       │
│   Triggered 2026-06-04 02:30 UTC | View trend → | Mute 7d → │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ ⓘ Citation F1: data insufficient (n=12 < 30 required)        │
│   No alert evaluated — see 'Generate more eval samples →'    │
└──────────────────────────────────────────────────────────────┘
```

### 9. Dashboard endpoint

```
GET /v1/libraries/{lib}/eval/alerts?status=active
GET /v1/libraries/{lib}/eval/alerts?status=all&days=30
GET /v1/alerts?status=active                          # 跨库元视图（§16.6 例外，见 ADR-0023）
POST /v1/libraries/{lib}/eval/alerts/{id}/mute        # 人工抑制 N 天
POST /v1/libraries/{lib}/eval/alerts/evaluate         # 手动触发评估（debug）
```

返回模型：

```python
class Alert(BaseModel):
    id: str
    library_id: str
    rule: str
    severity: Literal["info", "warning", "danger"]
    status: Literal["active", "recovered", "expired"]
    triggered_at: datetime
    recovered_at: datetime | None
    payload: dict
    notification_id: str | None
```

跨库 endpoint `/v1/alerts` 走 §16.6 例外条款（与 ADR-0023 ⌘K 搜索同性
质 — L5 编排层只读元视图）。

### 10. Mute（人工抑制）

研究员在做大幅实验（例如刚换 Embedder）时需要静音 N 天，避免 false alarm
刷屏：

```python
class AlertMute(BaseModel):
    library_id: str
    rule: str | Literal["*"]                       # "*" = 整库静音
    until: datetime
    reason: str
    created_by: str                                # principal kind/id
    created_at: datetime
```

evaluator 评估每条 rule 前先查 mute 是否存在。Mute 不阻止 alert 写表，但
**suppress notification** — 这样事后看 dashboard 还能知道「那段时间其实
有异常」。

### 11. 实现位置

```
packages/evaluation/
├── alerts.py                    # 主路径
│   ├── AlertEvaluator             # 协调一组 rules
│   ├── AlertRule (Protocol)       # 单条 rule 接口
│   ├── VarWeeklyDropRule
│   ├── CitationF1WeeklyDropRule
│   ├── P95LatencyWeeklyRiseRule
│   ├── DailyCostThresholdRule(threshold=0.8)
│   └── DailyCostThresholdRule(threshold=1.0)
├── alerts_repo.py               # PostgreSQL CRUD
└── snapshot.py                  # 已存在（BACKEND_ROADMAP §3.8 Gap 1）

apps/worker/jobs/
└── eval_alert_evaluator.py      # cron 02:30 入口

apps/api/routes/
└── eval_alerts.py               # 5 个端点
```

Rule Protocol：

```python
class AlertRule(Protocol):
    rule_id: str
    severity: Literal["info", "warning", "danger"]

    async def evaluate(
        self,
        library_id: str,
        snapshots: list[EvalSnapshot],
        cost_today: LibraryDailyCost,
        now: datetime,
    ) -> EvaluationOutcome: ...

    def is_recovered(self, active_alert: Alert, today: MetricSample) -> bool: ...
```

`EvaluationOutcome` 是 sum type：`Trigger(payload) | Ok | Skip(reason)`，
evaluator 根据 outcome 与现有 active alert 状态机决定下一步。

## Consequences

### Positive

- **Dashboard banner 一查就有** — 顶部 banner 直接 `GET /v1/libraries/{lib}/eval/
  alerts?status=active`，无需混合查多种聚合表。
- **per-Library 隔离** — 一个 Library 异常不污染其他 Library 的视图。
- **与 ADR-0011 通知中心 解耦但联动** — alerts 表是状态视图，notifications
  表是事件流；alert.notification_id 关联两者。
- **冷启动友好** — 14 天观察期避免「上线第一周告警刷屏」的常见运维痛苦。
- **小样本可识别** — `not_enough_data` 在 UI 上明确，不会被误读为「VAR 良好」。
- **5 条规则 v1 覆盖全部 4 KPI**（VAR / Citation F1 / P95 / cost），与 PRD §6 S8
  和 PRD §14.3 D7.6 KPI 卡列表完全对齐。

### Negative

- **每天 02:30 一个新 worker job** — 多一个 cron 故障点；缓解：失败时 log
  + 写 worker_failures notification（依赖 ADR-0011 已有的 worker 失败通知通道）。
- **5 个新 API endpoint** — 与 §3.8 Gap 1 的 3 个 endpoint 累加，eval 路由
  共 8 个，但都在 `apps/api/routes/eval*.py` 下分文件，可控。
- **alerts 表 + index** 的写入路径要保证 `UNIQUE WHERE status='active'` 偏序
  索引正确（Postgres ≥ 9.0 支持）。

### Risks

| 风险 | 缓解 |
|---|---|
| 评测集小导致指标抖动 → 误告警 | `sample_size ≥ 30` 才参与告警；否则标 `not_enough_data` |
| 第一天部署时无历史 | 14 天 cold start 期；前 7 天完全不评估周环比；7–13 天 dry-run 只 log |
| 同一 rule 一天内多次状态切换（active→ok→active） | 抑制策略：`UNIQUE WHERE status='active'` + 只在状态切换写通知；同一日不会重复发 |
| LLM-Judge 不稳定（PRD §13.5）导致 VAR 抖动 | `compute_var` 使用双 judge 取均值（PRD §13.5）；alert 阈值容忍 5pp 已含此噪声 |
| 用户主动重训 / 切 Embedder 触发集体告警 | Mute 机制（§10）；UI 在 Settings 切 Embedder 时弹 prompt 「自动 mute 7 天？」 |
| Cron 漂移 / 时区错乱 | 所有时间戳存 `TIMESTAMPTZ`；02:30 是 UTC；用户时区只在 UI 渲染层做转换 |
| alerts 表无限增长 | 90 天前 status='recovered' 的记录归档到 `alerts_archive`（dedicated job，nightly） |
| 全局 `/v1/alerts` 端点权限误用 | v1 单租户假设；M8 多租户时引入 user_id 过滤 + RBAC（与 ADR-0023 §11 同步演进） |

### Trade-offs

**为什么不上 Prometheus AlertManager**：

- 业务指标（VAR / Citation F1）的来源是 Postgres `eval_snapshots`，不是
  Prometheus scrape；强行把它推到 Prometheus 是引入第二个 source of truth。
- AlertManager 的去重 / 静音功能很强，但我们的 5 条规则简单到不需要。
- M6 后期如果 Grafana 已经接 Postgres datasource（PRD §13.2「Grafana
  dashboard：VAR 趋势 …」），可以**评估** Grafana Alerting（基于 SQL 查询）
  替代本 ADR 的 evaluator 进程；保留为 Open Question §3。
- 当前的 evaluator 是 ~200 行 Python，工程量低于引入新基础设施。

**为什么 alerts 与 notifications 是两个表**：

- notifications 是**事件流**（不可变），按时间排序，UI 顶栏渲染未读红点
- alerts 是**状态视图**（可更新），按 (library_id, rule) 唯一，UI Dashboard
  渲染 banner
- 同一份信息两份存储有重复，但查询模式不同；alerts.notification_id 关联两者

**为什么 cold start 是 14 天而不是 7 天 / 30 天**：

- 7 天：刚跑完一个 7-day window 就开始告警，previous_window 还是 cold
  start 期，对比基准不稳
- 30 天：太长，新 Library 用户上线 1 个月才看到 alert，体验差
- 14 天 = 2 周 = 1 个完整周环比基准

### 4 条 alerts vs 多 alerts

未来扩展空间（v1.1 候选）：

- `kg_freshness_stale`：community summary > 7 天未更新且文档增量 ≥ 50（与
  PRD §16.7 Stale community 状态一致 — 状态机已写 status，alert 是补充）
- `embedding_dim_mismatch`：用户切 Embedder 后存在跨维度索引（与 ADR-0012
  per-Library 配置覆盖联动）
- `hypothesis_calibration_drift`：Spearman ρ 跌破 0.5（与 ADR-0020 联动）

v1 不做，避免规则过多用户麻木。每条新规则需要 ADR amendment 走过 trade-off
评审。

## Alternatives Considered

| 方案 | 拒绝原因 |
|---|---|
| 实时告警（每次 eval 完成立即评估） | 单点噪声敏感；且 eval 跑频率本身就是 per-PR / nightly，与「每日 02:30」一致 |
| 每周一次评估 | 工作日异常 5 天后才告警，事故响应慢 |
| 不做自动恢复（只能手动 close） | active alert 永远挂着；用户麻木；Dashboard banner 永远红 |
| 1 天内连续触发就 OK（不要 2 天连续恢复） | 单日反弹是噪声；2 天是最小可信门槛 |
| 阈值写死 5pp / 50% / 80% / 100% 不可配 | 不同 Library 数据规模差异大（医学库 vs 玩具库），需要 per-Library 调；保留为 Open Question §1 |
| 只写 notifications 不开 alerts 表 | 找当前哪些规则在 active 要 group by + max（time）扫全表，慢；alerts 是 denormalized 状态视图 |
| 每个 alert 类型写一张专表 | 5 张表 schema 重复；alerts 一张表 + rule discriminator 列即可 |
| Prometheus + AlertManager | 引入第二套基础设施；业务指标的 source of truth 在 Postgres |
| 全局聚合告警（跨 Library） | 噪声平均；与 PRD §13.2「按 Library 分别告警」冲突 |
| Cold start 期完全 silent（log 都不打） | 期内异常无痕迹；14 天后看不到 cold start 期间的指标走势 |

## Open Questions

1. **per-Library 阈值可配化** — 当前所有 Library 共享 5pp / 50% / 80% / 100%
   阈值。是否把它们也纳入 `LibraryConfig`（与 ADR-0012 联动）？v1 不做，
   v1.1 评估。
2. **LLM-judge 双 judge 一致性低时** — PRD §13.5「双 LLM 独立打分取均值」，
   但如果两 judge 偏差 > 0.2，是否标 `judge_disagreement` 跳过本日 alert？
   保留 Open Question。
3. **是否切到 Grafana Alerting 替代独立 evaluator** — M6 后端 Grafana 接
   Postgres datasource 后再评估；切换不破坏 alerts 表 schema。
4. **mute 的粒度** — 当前 (library_id, rule) 或整库；是否需要 (library_id, rule,
   metric_value_range) 的更细粒度？v1 不做。
5. **alert digest** — 多条 alert 合并成一条「daily digest」邮件 / IM 通知？v1
   只做内站 notifications；外发渠道是 v2 工作。

## 与其他 ADR 的关系

- **ADR-0011 通知中心**：alerts 触发时写 `notifications`，type=`alert_triggered`/
  `alert_recovered`/`alert_re_triggered`；本 ADR 不重复定义通知存储与 SSE 拉取，
  完全复用 ADR-0011 已选 Postgres 表 + SSE pull。
- **ADR-0013 Library 状态机**：Library 状态（Healthy / Indexing / Stale community）
  与 alerts 是正交维度 — 状态机是「能不能用」，alerts 是「质量在不在退化」。
  Stale community 在 PRD §16.7 已是状态而非 alert，不在本 ADR 5 规则内。
- **ADR-0015 Daily Cost Cap**：`daily_cost_approaching_cap` / `daily_cost_exceeded_cap`
  两条规则的触发数据来自 ADR-0015 写入的 `library_daily_cost` 表；
  本 ADR 不重写 cost 累积逻辑，只读这张表生成 alert 视图。
- **ADR-0016 VAR 计算口径**：alerts 评估 VAR 直接读 `eval_snapshots` 中
  `metric='var'` 的值，VAR 怎么算是 ADR-0016 的事。如果 ADR-0016 改算法，
  alert 阈值（5pp）可能要重新校准 — 是 amendment 触发条件。
- **ADR-0008 Context Management**：Eval Dashboard 与 Conversation 共享 SSE
  通知通道，但 alerts 不与 conversation 流绑定 — alerts 是 Library 维度，
  conversation 是 Library 内子维度。
- **ADR-0023 ⌘K 跨资源搜索**：`/v1/alerts?status=active` 跨 Library 元视图
  与 ADR-0023 的 library 元数据搜索是同一类 §16.6 例外。

## References

- PRD §6 S8 Eval Dashboard（KPI 卡 + 告警 banner 来源）
- PRD §13.2 Alerting（VAR 周环比下跌 > 5pp 来源）
- PRD §13.5 风险登记（评测集过小 / LLM-Judge 不稳定）
- PRD §14.3 D7.6（VAR 周环比下跌 > 5pp 顶部告警 banner）
- PRD §16.6 Library 维度纪律（per-Library 告警合规依据）
- PRD §16.7 Library 状态枚举（与 alerts 的边界）
- PRD §17 R01（与 ADR-0015 Cost Cap 的协同）
- BACKEND_ROADMAP §3.8 Gap 2（实现位置定义）
- BACKEND_ROADMAP §3.2 Gap 4（VAR 与其他 KPI 聚合）
- BACKEND_ROADMAP §7 BR04（VAR 反馈样本少导致指标抖动 — 缓解依据）
- `packages/evaluation/alerts.py`（新）
- `packages/evaluation/alerts_repo.py`（新）
- `packages/evaluation/snapshot.py`（已存在）
- `apps/worker/jobs/eval_alert_evaluator.py`（新；cron 02:30）
- `apps/api/routes/eval_alerts.py`（新）
- ADR-0011 — Notification Center 存储与传输
- ADR-0015 — per-Library Daily Cost Cap
