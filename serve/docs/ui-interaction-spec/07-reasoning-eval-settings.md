# 07 · 跨文献推理 / 评测仪表 / 设置 — 交互规范

> 范围：S7 Reasoning（PathVisualization / EvidenceTimeline / HypothesisCard）、S8 Eval（KPICard / TrendBarChart / FailureCaseTable / AlertBanner / QualityKPIPanel）、Dashboard 元素（LibraryCard / RecentActivityItem）、Settings（LLMRouterPicker / EmbedderPicker / BudgetSettingsForm / SchemaEditor / FailedErrorPopover / CostMeter）
> 适用：RAG-KG Copilot 前端（Vue 3.4 + Pinia + Naive UI + UnoCSS + ECharts 5）
> 原则：业务层只用 `components/domain/*` 域组件 + `components/base/*` 原子；所有数值必须显示阈值上下文；危险操作必须二次确认；budget 是硬墙不是软提示。

---

## §52 PathVisualization · 多跳推理路径

> 文件：`components/domain/reasoning/PathVisualization.vue`
> 图：`052-03-ac-path-visualization-reasoning.png`

### 视觉
横向 3-hop 链：`Concept (GraphRAG) — uses_method → Method (Community summary) — extended_by → Author (Tu et al. 2025) — evaluates_on → Dataset (PrimeKG)`。
- 节点 = 圆角胶囊（radius `card` 14）`bg-surface` + 6 px 左侧实心圆点（KG entity 色：`kg-concept` 紫 / `kg-method` 青 / `kg-author` 黄 / `kg-dataset` 橙）。
- 节点内：标签（11 px、mono、`text-secondary`）+ 主体名（14 px、`text-primary`）。
- 边 = 1.5 px 实线 + 中部小标签 `uses_method`（11 px、mono、`text-tertiary`）。
- 顶部标题：`Best meta-path · 3 hops · confidence 0.78`（confidence 用 mono；< 0.5 改红）。
- 底部 `Conclusion` 段：14 px 正文 + 行尾跟 `[1] [3] [7] [12]` CitationChip（info-cyan）。

### 状态
default / hover-node（边框 brand-500、`shadow-md`、显示 tooltip 度数 + 上次出现年份）/ selected-path（整条链高亮、其他链褪到 30% 透明）/ collapsed（>5 hops 中间折叠成 `… +3 more`）/ no-path（空态卡 + "Generate reasoning"）。

### 交互
1. 节点 hover → tooltip（degree / 关联 chunks 数 / KG 跳转链接）。
2. 节点 click → 右侧抽屉 `EntityPanel`（属性 / 别名 / 关联 chunks 列表 → 点击进 EvidenceCard）。
3. 边 hover → 显示 `relation_type` + `support_count`；click → 列出支撑该 relation 的 chunks。
4. 整条 path 右上角下拉：Validate / Refute / Generate hypothesis / Open in KG Canvas。
5. 多 path 视图：纵向堆叠 3 条 best paths，可勾选 compare（高亮交集节点用 brand-100 底）。

### A11y
- 整图加 `role="graphics-document"` + `aria-label="Reasoning path with 3 hops, confidence 0.78"`。
- 键盘：Tab 进入图 → 方向键在节点间跳；Enter 展开节点详情；Esc 退出。
- 颜色不是唯一信息：节点左侧除颜色外加 entity-type 缩写图标（C / M / A / D）。

### 动效
- 渲染时 stagger 70 ms 自左向右淡入；边走线动画 360 ms `ease-out`。
- selected path 切换：未选中链 200 ms 渐变到 0.3 alpha；选中链 sticky。
- 折叠/展开 `… +3 more`：280 ms width spring。

### Vue 实现
- 库：**cytoscape 3.x + cytoscape-dagre**（横向 rankDir = LR；node 用 HTML overlay 渲染胶囊以复用 UnoCSS class，可选 `cytoscape-popper`）。
- 数据接口：`GET /lib/:id/reason` → `{ paths: Path[] }`，`Path = { id, nodes: Entity[], edges: Relation[], confidence, conclusion, citations }`。
- store：`useReasoningStore` 持 `paths / selectedPathId / hoveredNodeId`。
- 暴露 `<PathVisualization :paths :selected @select @node-click />`。
- 关键代码骨架：

```ts
// usePathLayout.ts
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
cytoscape.use(dagre)
export function mountPath(el: HTMLElement, path: Path) {
  return cytoscape({
    container: el,
    elements: toCyElements(path),
    layout: { name: 'dagre', rankDir: 'LR', nodeSep: 32, rankSep: 64 },
    style: nodeStyle, // 用 mappers 把 entity_type → kg-* token
    wheelSensitivity: 0.15,
  })
}
```

### 联动
- `colorStore.entityTypes` 单一源 → SchemaEditor 改色后此处 5 ms 内重渲染。
- click 节点 → `router.push({ path: '/lib/:id/kg', query: { focus: entityId } })`。
- 选中 path → HypothesisCard 自动以该 path 为 grounding 触发 `/hypothesize`。

---

### UI 参数（来自 UI_PROMPTS §03-AC）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 672 × 320 |
| 圆角 | 14 |
| 背景 / 描边 | `bg-surface` #FFFFFF / 1 `border-subtle` #E4E4E0 |
| padding | 24 |
| 阴影 | shadow-sm |
| 标题 | h3 20/24.2, 600，`text-primary` #1A1A1A |
| 路径节点 | 横向单行均匀分布；矩形高度统一 52；宽度按内容：`Concept 112` / `Method 152` / `Author 128` / `Dataset 152` |
| 关系标签 | body-sm 13/15.7, 400, `text-tertiary` #8C8C82；形如 "— uses_method →" |
| 节点圆角 / 配色 | 沿用 KG node（03-Q），实体类型色描边 + 同色 dot |
| 路径选中描边 | 2 `brand-500` #4F46E4 + `brand-50` #EDF0FF 4 左边轨（与 HypothesisCard 选中规则一致） |
| confidence chip | 标题尾随 "confidence 0.78"，mono 13/20；建议 pill 999 `bg-subtle` #F4F4F1 包裹 |
| 分隔线 | 1 px `border-subtle` #E4E4E0 |
| CONCLUSION label | meta 11/13.3, 500, uppercase, `text-tertiary` |
| 结论正文 | body 14/22, 400, `text-primary` #1A1A1A；inline CitationChip 用 info 青 |

## §53 EvidenceTimeline · 横向证据时间轴

> 文件：`components/domain/reasoning/EvidenceTimeline.vue`
> 图：`053-03-ad-evidence-timeline.png`

### 视觉
- 顶部标题 `Evidence timeline · 4 papers across the 3 hops`。
- 横线 1 px `border-default` 贯穿；4 个圆点（brand-500、Ø 12 px）按时间分布（2024-04 / 2024-09 / 2025-03 / 2025-08）。
- 每个圆点正下方一张 mini 证据卡：作者 `Gao, Y. et al.` 14 px、引用片段 13 px 限 2 行省略、`chunk_9f3a1b2c` mono 12 px 链接。
- 底部 CTA `Open all 4 in Chat →`（brand-500 文字按钮）。

### 状态
default / hover-chip（卡片 `shadow-md` + 上移 2 px）/ selected（border brand-500、底色 brand-100）/ empty（空态线 + "No evidence yet"）/ year-cluster（同年多条折叠成 `2025-03 ×3` chip，hover 弹气泡列举）。

### 交互
1. 点 chip → 右侧 `EvidenceCard`（全文、metadata、Open chunk）。
2. 横向滚动：>10 条启用拖拽 + ECharts dataZoom（轨道下方 8 px 高 mini bar）。
3. 时间粒度切换：年 / 季 / 月（segmented tab）。
4. 多选模式：长按或勾选 → 顶部出现 `Compare (3) · Open in Chat`。

### A11y
- 列表层 `role="list"`，chip `role="listitem"` + `aria-label="Gao 2024-04, chunk_9f3a1b2c"`。
- 键盘：Left/Right 在 chip 间跳；Enter 打开详情。

### 动效
- 入场：圆点 spring 弹入（stagger 90 ms），mini 卡 fade-up 200 ms。
- 选中：圆点 scale 1 → 1.25 220 ms。

### Vue 实现
- 库：**ECharts custom series**（避免引入 vis-timeline 230 KB）。x 轴 time scale，渲染函数返回圆点 + 文本，DOM tooltip 用 vue-echarts 的 `tooltip.formatter` 返回 HTML。
- 数据：`Evidence[] = { id, paperId, authors, year, month, chunkId, snippet }`。
- props：`<EvidenceTimeline :items :selected :granularity @select @compare />`。

### 联动
- 与 PathVisualization 同源：`selectedPathId` 变化 → timeline 仅显示该 path 的 evidence。
- 多选 → Chat 重放 `/chat?evidence=ids`，Chat 自动 ground 这些 chunks。

---

### UI 参数（来自 UI_PROMPTS §03-AD）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 672 × 252 |
| 圆角 / 描边 / 背景 | 14 / 1 `border-subtle` #E4E4E0 / `bg-surface` #FFFFFF |
| padding | 24 |
| 阴影 | shadow-sm |
| 标题 | h3 20/24.2, 600 |
| 横轴布局 | 4 列年份均匀分布在一条横向基线上 |
| 时间轴线 | 1 px 垂直中心轴（按 PROMPT 文字："vertical center axis"），色 `brand-200` #B2BCF4 — 注：原文写 vertical，文档语义为横向时间轴，按"水平轴线" 1 px `brand-200` 实现（冲突标注） |
| 年份节点 dot | 12 × 12 圆点 `brand-500` #4F46E4 |
| 年份字号 | caption 12/14.5, 400，`text-tertiary` #8C8C82；如 "2024-04" |
| Evidence chip 卡 | 152 × 96 EvidenceCard 变体，内含 author + quote excerpt + `chunk_id` chip |
| 卡内字号 | author body-sm 13/15.7；quote body-sm；chunk_id mono 13/20 |
| 底部 CTA | ghost "Open all 4 in Chat →" body-sm 13/15.7, 600, `brand-600` #3B30D9 |

## §54 HypothesisCard · 假设卡（三轴评分）

> 文件：`components/domain/reasoning/HypothesisCard.vue`
> 图：`054-03-ae-hypothesis-card.png`

### 视觉
卡片宽 ≈ 720，padding 24，radius `card` 14。
- 左上 `#1` 序号 chip（brand-100 底、brand-600 字、mono）。
- 主体 16 px 假设语句，行高 1.6。
- 三轴评分（**3 个 progress bar 而非 radar**——更易扫读）：
  - `NOVELTY 0.85` / `CONFIDENCE 0.72` / `FALSIFIABILITY 0.78`。
  - bar 高 6 px、track `bg-subtle`、fill brand-500、右侧数值 mono 13 px。
  - 阈值色映射：< 0.3 danger、0.3-0.6 warning、> 0.6 brand。
- 底部 `3 supporting paths in KG · grounded in 4 papers · 12 chunks` 12 px `text-secondary`。

### 状态
Default / Compact（宽 < 480，去掉评分细节，仅显示标题 + 3 个数字 chip + 行内 meta）/ Selected（border brand-500 2 px + brand-100 底）/ Validated（左缘 4 px success bar + 角标 ✓）/ Refuted（左缘 danger bar + 角标 ✕，文字打删除线 30% 不透明）/ Generating（骨架屏 + 流式打字光标）。

### 交互
1. 卡片右上隐藏菜单：Validate / Refute / Save / Discuss in chat / Export markdown。
2. 正反 evidence 默认折叠：底栏 `Show 4 supporting · 1 contradicting`，展开后两栏列表（success / danger 左缘）。
3. Validate / Refute 是**二次确认**：弹 popover `This will mark hypothesis #1 as validated based on N supporting chunks. Continue?` → Confirm。
4. Discuss in chat → 在 ChatPanel 预填 `Re: hypothesis #1 — ...` 引文块。

### A11y
- 三轴 bar 各加 `role="progressbar"` + `aria-valuenow / min=0 / max=1` + `aria-label="Novelty 0.85"`。
- Validated / Refuted 不只用颜色：额外文字角标。
- 整卡 `role="article"` + `aria-labelledby` 指向首行。

### 动效
- 流式生成：评分 0 → 目标值 700 ms `ease-out` 数字滚动 + bar 同步增长。
- Validate 切换：4 px 左缘 success bar 从 0 → 4 240 ms slide-in；角标 spring。

### Vue 实现
- 内嵌 mini sparkline 用 ECharts；评分 bar 用纯 CSS（无需图表）。
- `<HypothesisCard :hypothesis :variant="'default'|'compact'|'selected'" @validate @refute @save @discuss />`。
- 数据：`{ id, statement, scores: {novelty, confidence, falsifiability}, supporting: Evidence[], contradicting: Evidence[], status: 'pending'|'validated'|'refuted' }`。

### 联动
- Validate → 调 `POST /hypothesize/:id/validate` → 全局 toast + Eval 看板的 `hypothesis_validation_rate` KPI +1。
- Refute → 标记后 contradiction 进入 FailureCaseTable 的 `human_refuted` 集。
- Discuss → 跳 Chat 并预填 grounding。

---

### UI 参数（来自 UI_PROMPTS §03-AE）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 656 × 180（标准） / 656 × 88（compact） |
| 圆角 / 描边 / 背景 | 14 / 1 `border-subtle` #E4E4E0 / `bg-surface` #FFFFFF |
| padding | 20 |
| gap | 12 |
| 阴影 | shadow-sm |
| 排名 pill | 36 × 22，radius pill 999，`bg brand-500` #4F46E4，文字白 body-sm 13/15.7, 600，如 "#1" |
| 假设标题 | body 14/22, 400，`text-primary` #1A1A1A，最多 4 行；inline CitationChip |
| 三轴评分行 | 3 列，每列宽 120 |
| 评分标签 | meta 11/13.3, 500, uppercase, `text-tertiary` #8C8C82（novelty / confidence / verifiability） |
| 评分条 track | 120 × 4，radius pill 999，`bg-muted` #EAEAE5 |
| 评分条 fill | `brand-500` #4F46E4 至 value% |
| 评分数字 | mono 13/20, 600，右对齐（如 "0.85"） |
| 底部 caption | `text-tertiary` 12/14.5, 400（"3 supporting paths in KG · grounded in 4 papers · 12 chunks"） |
| 选中态 | 2 px `brand-500` outline + `brand-50` #EDF0FF 左 4 px 边轨 |
| Validate / Refute / Save 按钮 | 文档既有交互定义；PROMPT 未给精确尺寸，沿用 base/button 标准（高 32，圆角 10）— `—` |

## §55 KPICard · 关键指标卡

> 文件：`components/domain/eval/KPICard.vue`
> 图：`055-03-af-kpi-card.png`

### 视觉
单卡布局：
- Label 11 px UPPER `text-tertiary`：`VAR · VALID ANSWER RATE`。
- 主体数值 `display`（36 px）mono、`text-primary`：`76.4%`。
- 趋势 chip：`↗ 2.1pp / week`（success）/ `↘ 0.04 / week`（danger）/ `→ 0`（neutral）。
- 目标行：`target ≥ 75% · v1.0 GA criterion` + 右侧 `✓ on track` success chip / `⚠ at risk` warning / `✕ below target` danger。
- 可选内嵌 sparkline（高 28 px、无轴、贯穿底部）。

### 状态
on-track / at-risk / below-target / loading（骨架）/ no-data（占位 `—` + 提示 "Run evaluation to populate"）。
- 阈值颜色映射：VAR < 75 red、Citation F1 < 0.85 red、P95 > 20 s red、$ > 0.10 red。

### 交互
1. hover 卡 → `shadow-md`，趋势 chip 变成可点击（点击进 TrendBarChart 详情页）。
2. 右上角 `…` → Remove from panel / Pin / Set custom threshold / Export PNG。
3. 点主数值 → 跳 `/lib/:id/eval/:metric` 详情。

### A11y
- 数值 `aria-label="VAR is 76.4 percent, target 75 percent, on track"`。
- chip 颜色 + 箭头 + 文字三重冗余。

### 动效
- 数值变化：120 ms 数字滚动（`@number-flip-vue/vue3`）。
- 阈值跨越：on-track → below 时整卡 280 ms `box-shadow` 渲染 danger 内阴影 1 次（呼吸）。

### Vue 实现
- 纯组件，无图表依赖；sparkline 用 ECharts 共享实例池（minSize: 80×28）。
- `<KPICard :label :value :unit :delta :target :targetComparator :status @click />`。

### 联动
- 状态变 `at-risk` / `below-target` → 自动派发 `evalStore.alerts.push(...)` → AlertBanner 渲染。
- pin / unpin / 重排 → 写 `userPrefs.kpiPanelLayout`。

---

### UI 参数（来自 UI_PROMPTS §03-AF）

| 类别 | 值 |
|---|---|
| 卡宽 / 高 | 336 × 128（注：与"通用 KPI Card 280 × 132"对照规则有冲突，按本批 PROMPT 取 336 × 128 — 冲突标注） |
| 圆角 | 14 |
| 背景 / 描边 | `bg-surface` #FFFFFF / 1 `border-subtle` #E4E4E0 |
| padding | 20 |
| 阴影 | shadow-sm |
| 顶部 label | meta 11/13.3, 500, uppercase, `text-tertiary` #8C8C82（如 "VAR · Valid Answer Rate"） |
| 大数字 | h1 28/33.9, 700, `text-primary` #1A1A1A，tabular-nums |
| 单位 | 与大数字同行 inline（如 "%"），同字号或视觉次级 |
| 同环比 chip | body-sm 13/15.7，arrow + 色带；上涨 `success-50` #EBFCF5 bg / `success-700` #047856 text；下跌 `danger-50` #FDF1F1 / `danger-700` #B91B1B；arrow ↑/↓ 600 weight |
| sparkline 高 | — （本 PROMPT 未画 sparkline，KPI card 4 卡水平排列；保留位 32，按 v1.0 不实现） |
| 底部辅助行 | body-sm 13/15.7, 400, `text-tertiary`（如 "target ≥ 75% · v1.0 GA criterion · ✓ on track"） |
| 排列示例 | 4 卡水平：VAR · Citation F1 · P95 latency · $/question |

## §56 TrendBarChart · 趋势柱图

> 文件：`components/domain/eval/TrendBarChart.vue`
> 图：`056-03-ag-trend-bar-chart.png`

### 视觉
- 标题 `VAR · daily · last 30 days`、副标 `smoke set · 10-question rolling window · target line at 75%` 12 px。
- bar：brand-300 默认、当天 brand-600 高亮；阴线（last week）描边 `border-strong` dashed 浅色对照。
- 阈值线：75% 处 1 px dashed warning + 右端 label `75%`。
- 左侧 y 轴仅 50% / 100% 两 tick；x 轴日期每 7 天一 tick。
- 底图例：实心圆点 `this week` / 空心圆 `last week`。

### 状态
default / dataZoom-active（拖拽时显示更密 tick）/ no-data（空态图 + "Run nightly eval to populate"）/ comparing（两周叠加）。

### 交互
1. hover bar → tooltip：日期 / 当周值 / 上周值 / Δ / 触发原因（如 ingest 大批进入）。
2. brush（按住 Shift 拖拽）→ 选范围 → "Inspect 7 failed cases in range"。
3. 双击 → 重置 zoom。
4. 右上角 toggle：bar / line / 累计；导出 PNG / CSV。

### A11y
- chart container `role="img"` + `aria-label="VAR daily chart, ranging 60% to 95% over 30 days, target 75%"`。
- 提供 `Show data table` toggle → 展开同源 `<table>` 视障替代。

### 动效
- bar 入场 stagger 30 ms；切换周比 200 ms morph。

### Vue 实现
- 库：**ECharts 5 + vue-echarts**；bar series + markLine (target) + dataZoom（slider + inside）+ visualMap（阈值染色：< target 自动 danger 描边）。
- props：`<TrendBarChart :metric :range :compareWith="'last_week'|'last_month'|null" />`，数据通过 `evalStore.series[metric]` 拉。

### 联动
- 与 KPICard 双向：卡 click → 此处打开该 metric 详情；brush 范围 → 给 FailureCaseTable 加 `dateRange` 过滤。

---

### UI 参数（来自 UI_PROMPTS §03-AG）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 864 × 280 |
| 圆角 / 描边 / 背景 | 14 / 1 `border-subtle` #E4E4E0 / `bg-surface` #FFFFFF |
| padding | 24 |
| 阴影 | shadow-sm |
| 标题 | h3 20/24.2, 600（"VAR · daily · last 30 days"） |
| 副标题 meta | body-sm 13/15.7, 400, `text-tertiary` #8C8C82 |
| 柱数 | ~12 vertical bars |
| 单 bar 宽 | 56 |
| bar 间距 | 均匀分布；按 12 柱 + 56 w 估算（PROMPT 未给数字，按等距） |
| bar 圆角顶 | PROMPT 未指定，沿用 Naive UI / ECharts 默认 borderRadius `[2,2,0,0]` |
| bar fill | `brand-500` #4F46E4 线性渐变到顶部 `brand-300` #8D9FFF |
| hover bar | `brand-700` #2A1FAF |
| target line | 1 px 虚线 `warning-500` #F59E0A，水平 "75%" |
| target label | 右边缘 "75%"，caption 12/14.5, 400, `warning-700` #B45208 |
| X 轴标签 | caption 12/14.5, 400, `text-tertiary`（"May 1 / May 8 / …"） |
| 轴线 / 网格 | 无 Y 轴刻度；50% / 100% 两条淡水平网格线 `border-subtle` #E4E4E0 |
| dataZoom 高 | — （本图无 dataZoom；如需后续加，按 ECharts 默认 16） |
| 图例 | body-sm 12/14.5, 400, `text-tertiary`（"● this week · ○ last week"） |

## §57 FailureCaseTable · 失败用例表

> 文件：`components/domain/eval/FailureCaseTable.vue`
> 图：`057-03-ah-failure-case-table.png`

### 视觉
- 标题 `Recent eval failures · click to inspect trace in Langfuse`。
- 列：`QID` / `SET`（multihop / qa / comparison / kg_reasoning chip）/ `QUESTION (TRUNCATED)` / `FAILURE`（彩色 chip：`citation_invalid` danger-100、`no_evidence` warning-100、`hallucination` danger-200、`incomplete_reasoning` warning-200）/ `VAR Δ` 红字 mono / `COST` mono。
- 底部 CTA `View all 14 failures in Langfuse →` brand-500。
- 行高 44 px；hover row `bg-subtle`。

### 状态
default / row-hover / row-expanded（48 px 上方原行 + 下方展开区 240 px 含 trace 子卡）/ multi-select（前置 checkbox 列；顶栏出现 `Tag (3) · Add to retrain set · Re-run`）/ empty / loading（骨架行）。

### 交互
1. 行点击 → 展开 trace 子卡：`question / retrieved_chunks (折叠) / answer / expected / why_failed`（GPT judge 解释，mono 引用 chunk_id）。
2. failure chip 右键 / 点 → 跳 Langfuse trace（新窗口）。
3. 批量打标签：勾选 N 行 → 顶栏 `Tag as → [select category]` → 写入 `retrain_dataset.v?`。
4. `Add to retrain set` → 弹确认 + 选目标 dataset 版本。

### A11y
- table semantic + `<th scope="col">`；`aria-rowcount`、`aria-expanded` 行展开同步。
- 键盘：Up/Down 行移动、Space 选中、Enter 展开。

### 动效
- 展开 240 ms `ease-out` height + 内容 80 ms 延迟淡入。
- 多选 toolbar 从顶部 slide-down 200 ms。

### Vue 实现
- 库：**`@tanstack/vue-table` v8**（复用 §06 KGCanvas 旁的实现）+ TanStack 虚拟滚动（`@tanstack/vue-virtual`）应对 1k+ 行。
- props：`<FailureCaseTable :rows :selectable :pageSize @row-expand @bulk-tag @retrain />`。
- 数据 `EvalFailureRow = { qid, set, question, failure, var_delta, cost, trace_id, retrieved, answer, expected, why_failed }`。

### 联动
- 行 click → emit `replay` → Chat 跳 `/chat?replay=qid`，Chat 自动回放 retrieval。
- `bulk-tag` → 写 retrain dataset → BudgetSettingsForm 估算 retrain 成本预览。
- TrendBarChart brush → 此处 `dateRange` 过滤同步。

---

### UI 参数（来自 UI_PROMPTS §03-AH）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 864 × 248 |
| 圆角 / 描边 / 背景 | 14 / 1 `border-subtle` #E4E4E0 / `bg-surface` #FFFFFF |
| padding | 20 |
| 阴影 | shadow-sm |
| 标题 | h3 20/24.2, 600 |
| 表头行高 | 36 |
| 表头字 | mono caption 12/14.5, 400, uppercase, `text-tertiary` #8C8C82 |
| 数据行高 | 48 |
| 行 hover | `bg-subtle` #F4F4F1 |
| 行字 | body-sm 13/15.7, 400, `text-primary` #1A1A1A，数字 tabular-nums |
| 展开行内 padding | — （PROMPT 未给展开态；如需，沿用 Naive table expand 16） |
| 列宽建议（基于示例） | QID 120 / SET 96 / QUESTION（truncated） 360 / FAILURE 168 / VAR Δ 72 / COST 72；总 888 与表 864 略大，按内部 padding 收 24 — 冲突标注 |
| FAILURE chip | `danger-50` #FDF1F1 bg / `danger-700` #B91B1B text，body-sm 13/15.7 |
| 末行链接 | body-sm 13/15.7, 600, `brand-600` #3B30D9（"View all 14 failures in Langfuse →"） |

## §58 AlertBanner · 页面级横幅

> 文件：`components/domain/feedback/AlertBanner.vue`
> 图：`058-03-ai-alert-banner.png`

### 视觉
4 种 severity，统一 36 px 高、radius `card` 14：
- success（绿圈勾、`bg: success-50`、`border: success-300`）`All KPIs within target · last alert 9 days ago`。
- info（蓝圈 i、cyan-50）`New eval set 'multihop-v3' published. Run via Settings → Evaluation.`。
- warning（黄三角、warning-50）`Citation F1 has dropped 0.04 over 7 days — inspect failures`。
- danger（红禁、danger-50）`Ingest worker offline — uploads queued, will retry on reconnect`。
- 右端 `×` close（不可关 = 持久则隐藏 close）。

### 与 Toast 区别
| 维度 | Banner | Toast |
|---|---|---|
| 作用域 | page-scoped 持续 | global 临时 |
| 时长 | 直到状态消除 | 4 s 自动 |
| 位置 | 内容区顶部 sticky | 屏幕角落 |
| 触发 | 持续状态（budget exceeded、worker offline、阈值跌破） | 一次性反馈（保存成功、复制） |
| 可关 | 仅信息可关；阻塞性不可关 | 始终可关 |

### 状态
visible / dismissed / persistent（无 close）/ stacked（>1 时堆叠最多 3 条，第 4 条折叠为 `+N more`）。

### 交互
- 内嵌行内 CTA（`inspect failures` brand-500 文字按钮）。
- close 触发 `bannerStore.dismiss(id)` 写本地存储 7 天不再提示（仅 info / success）。
- danger 持续：close 隐藏，但状态恢复前每次进页面仍显示。

### A11y
- `role="alert"`（danger / warning）/ `role="status"`（info / success）。
- 不依赖颜色：icon + 文字双冗余。

### 动效
- 入场 220 ms slide-down + fade；dismiss 160 ms collapse。

### Vue 实现
- `<AlertBanner :severity :persistent :id :action @dismiss />`，全局 `<AlertBannerStack />` 放 AppShell main 顶。

### 联动
- KPIThreshold breach（来自 §55）→ Banner（warning）+ 链接到失败列表。
- CostMeter 超阈值（§67）→ 全局 danger Banner + 拦截重 LLM 调用按钮。

---

### UI 参数（来自 UI_PROMPTS §03-AI）

| 类别 | 值 |
|---|---|
| 整体宽 / 高 | 1376 × 40（容器内 full width） |
| 圆角 | 14（沿用 card；PROMPT 未给独立 banner 圆角，按容器） |
| padding | 16 |
| 行布局 | leading 状态 icon 20 + body-sm 600 首句 + body-sm `text-secondary` #515151 详情 + 末尾 dismiss "×" 20 |
| 左边色条宽 | — （PROMPT 未画 4 px 色条；建议加 4 px 与 tone 同色，本批未强制） |
| **info** | bg `info-50` #EBFDFF / text `info-700` #0E7490 / icon `info-500` #06B6D3（"ⓘ New eval set…"） |
| **success** | bg `success-50` #EBFCF5 / text `success-700` #047856 / icon `success-500` #10B881（"● All KPIs within target…"） |
| **warning** | bg `warning-50` #FFFAEB / text `warning-700` #B45208 / icon `warning-500` #F59E0A（"⚠ Citation F1…"） |
| **danger** | bg `danger-50` #FDF1F1 / text `danger-700` #B91B1B / icon `danger-500` #EE4444（"⊘ Ingest worker offline…"） |
| 首句字号 | body-sm 13/15.7, 600 |
| 详情字号 | body-sm 13/15.7, 400, `text-secondary` |
| 位置 | sticky 于 /eval 主列页面 header 之下 |

## §59 LibraryCard · 知识库卡

> 文件：`components/domain/dashboard/LibraryCard.vue`
> 图：`059-03-aj-library-card.png`

### 视觉
- 280 × 200，radius `card` 14，`bg-surface` + `border-default`、hover `shadow-md`。
- 顶部 `GraphRAG Lab` 18 px + `Healthy` success pill（右上）。
- 简述 13 px `text-secondary` 限 2 行。
- 4 指标矩阵：`DOCS 2,184 / CHUNKS 62.4k / ENTITIES 8,491 / TRIPLES 31.2k`（mono、Label UPPER 10 px tertiary）。
- 底栏：`Last activity · 14m ago`（`date-fns/formatRelative` 中文 locale 可切）+ 右下 `⋯` overflow。
- 旁边 `+ New Library` 虚框卡（dashed border、居中 + 图标）。

### 状态
default / hover（`shadow-md` + 2 px translateY、overflow `⋯` 浮出 → Open / Settings / Delete / Duplicate）/ Healthy / Indexing（顶部 1 px 不定进度条）/ Degraded（warning pill + 顶部告警条）/ Empty（Docs 0 时灰化矩阵 + `Upload to start`）。

### 交互
1. 整卡 click → `/lib/:id`（Dashboard）。
2. 设置图标 / Settings 行 → `/lib/:id/settings`。
3. Delete → Modal 二次确认 + 输入库名匹配后才允许（**危险操作必须二次确认**铁律）。
4. Healthy pill hover → tooltip 显示 8 指标摘要。

### A11y
- 整卡 `role="link"` + `aria-label="GraphRAG Lab library, 2184 documents, healthy"`。
- overflow menu 键盘可达。

### 动效
- hover 120 ms shadow + translate；indexing 顶部进度条 1.2 s loop。

### Vue 实现
- `<LibraryCard :library :variant="'card'|'new'" @open @settings @delete />`。
- `library.health` 由 `useLibraryStore` 同步（轮询 `/lib/:id/health` 30 s）。

### 联动
- click → 切换 `currentLibraryId`，触发 AppShell 二级导航重渲染。
- Health degraded → 该库 Dashboard 顶部自动挂 AlertBanner。

---

### UI 参数（来自 UI_PROMPTS §03-AJ）

| 类别 | 值 |
|---|---|
| 卡宽 / 高 | 320 × 220（grid 中 min 300, max 1fr） |
| 圆角 | 14 |
| 背景 / 描边 | `bg-surface` #FFFFFF / 1 `border-subtle` #E4E4E0 |
| padding | 20 |
| gap | 12 |
| hover 阴影 | shadow-md（0 4 px 12 px rgba(15,15,20,.06)） |
| 标题 | h3 20/24.2, 600, `text-primary` #1A1A1A |
| 状态 pill | "● Healthy" / "◐ Indexing" / "⚠ Stale community"，沿用 base/status-pill |
| 描述字号 | body-sm 13/15.7, 400, `text-secondary` #515151，2 行截断 |
| 统计网格 | 4 列 |
| 统计数字 | h2 22/26.6, 700, tabular-nums |
| 统计单位 | caption 12/14.5, 400, `text-tertiary` #8C8C82 |
| 底部 meta | body-sm 13/15.7, 400, `text-tertiary`（"Last activity · 14m ago"）+ 右侧 "⋯" kebab |
| count chip | 沿用通用 chip：radius 6，meta 11/13.3, 500 |
| "+ New Library" 变体 | 320 × 220，1.5 px dashed `border-default` #D3D3CE，bg `bg-canvas` #FAFAF9；中央 64 × 64 圆容器 `bg-subtle` #F4F4F1 + 大 "+" `brand-600` #3B30D9；标题 body 14, 600 "New Library"，caption `text-tertiary` |

## §60 RecentActivityItem · 最近活动项

> 文件：`components/domain/dashboard/RecentActivityItem.vue`
> 图：`060-03-ak-recent-activity-item.png`

### 视觉
列表行 16 px 垂直 padding：
- 左侧圆形图标背（36 px、success-100 / brand-100 / warning-100 等浅底）+ 动作图标（✓ / ✨ / ⚠）。
- 主行：`Review complete: "GraphRAG Survey"`（14 px、`text-primary`、引号内 italic）。
- 副行：`graphrag-survey · 3,142 words · 47 citations`（12 px `text-secondary`、mono 数字）。
- 右侧时间：`14m ago` 12 px tertiary。
- 项间 1 px `border-default` 分隔。

### 状态
default / hover（整行 `bg-subtle`、右侧 `→` 浮出）/ unread（左 3 px brand-500 竖条）/ failed（danger 图标 + danger-50 底）/ loading-skeleton。

### 交互
1. click → 跳活动详情（review / ingest / community 各跳不同路由）。
2. 长按 / 右键 → 复制链接 / Mark as read / Hide。
3. failed item hover → 弹 FailedErrorPopover（§66）。

### A11y
- `role="listitem"`；动词主语宾语合并 `aria-label="Review complete for GraphRAG Survey, 14 minutes ago"`。
- 时间附 `<time datetime="...">` 真实 ISO 时间。

### 动效
- 入场新项：高 0 → auto 200 ms + 左边 brand-500 闪烁 1 次。

### Vue 实现
- `<RecentActivityItem :activity />`，`activity = { id, actor, verb, object, meta, ts, status, route }`。
- 时间用 **`date-fns/formatRelative`**（包小、tree-shake；不引 dayjs 两套）。

### 联动
- 推流来自 SSE `/activity?lib=:id` → 顶部插入；与 NotificationCenter 共享底层 store。

---

### UI 参数（来自 UI_PROMPTS §03-AK）

| 类别 | 值 |
|---|---|
| 行高 | 56–72（响应内容） |
| padding | 12 |
| gap | 12 |
| 行 hover | `bg-subtle` #F4F4F1，radius 10 |
| 行分隔线 | 1 px 水平 divider，左 inset 12 |
| 前导 icon 容器 | 32 × 32 圆，配色按动作类型：`success-50` #EBFCF5 + check / `brand-50` #EDF0FF + sparkles / `warning-50` #FFFAEB + alert-triangle |
| 标题字号 | body 14/22, 600, `text-primary` #1A1A1A，1 行截断；可含 italic 600 引号工件名 |
| Meta 字号 | body-sm 13/15.7, 400, `text-tertiary` #8C8C82，middot · 分隔 |
| 末尾 relative time | caption 12/14.5, 400, `text-tertiary` #8C8C82，右对齐 |
| actor 头像 | — （本 PROMPT 未用 actor 头像；用 icon 容器代之） |

## §61 QualityKPIPanel · 质量看板 grid

> 文件：`components/domain/eval/QualityKPIPanel.vue`
> 图：`061-03-al-quality-kpi-panel.png`

### 视觉
- 卡片标题 `Quality at a glance`；2 列 grid（>1024 px 时 3 列、< 720 px 时 1 列）。
- 每格 = 紧凑 KPICard（去 sparkline、去 chip 边框，仅 label + value + delta 行）。
- 底栏 `Targets: VAR ≥ 75% · Citation F1 ≥ 0.85 · P95 ≤ 20s · $ ≤ 0.10` 11 px `text-tertiary`（**所有数值显示阈值上下文**铁律）。

### 状态
default / edit-mode（每格右上 6-dot drag handle + 红色 × 删除）/ add-metric（grid 末追加虚框 `+ Add metric`）/ saved-as-preset toast。

### 交互
1. 顶部 `Edit panel` 切换 edit-mode → 可拖拽重排 / 删除 / 添加。
2. 添加 → 弹 Sheet 列出所有可用 metric（按 category 折叠），可多选。
3. `Save as preset` → 命名后存为 `userPrefs.kpiPresets[]`，下次可一键加载。
4. 重置 → 回 v1.0 GA 默认 5 指标。

### A11y
- `role="region"` + `aria-labelledby`；拖拽用键盘备份方案（选中 + ↑↓ Move）。

### 动效
- edit-mode 进入 220 ms 抖动一次提示可拖；项 reorder 用 FLIP 280 ms。

### Vue 实现
- 拖拽：**vuedraggable@4**（SortableJS Vue 包）；启用 `handle: '.drag-handle'` + `animation: 200`。
- `<QualityKPIPanel :metrics :editable v-model:layout @save-preset />`。

### 联动
- 删除 metric → 仅影响当前 view，不删 backend 计算；preset 持久化 user-level。
- KPI 跨阈值 → AlertBanner 注入。

---

### UI 参数（来自 UI_PROMPTS §03-AL）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 384 × 320（或 ≥1024 时 2×2 / 1×4 响应网格） |
| 圆角 / 描边 / 背景 | 14 / 1 `border-subtle` #E4E4E0 / `bg-surface` #FFFFFF |
| padding | 24 |
| grid gap | 16 |
| 阴影 | shadow-sm |
| 标题 | h3 20/24.2, 600（"Quality at a glance"） |
| 每个 KPI Card min-w | — （在本 panel 内，按 4 项 1 列 / 2 列响应，每项无 min-w，撑满 panel 内可用宽） |
| KPI 行 label | meta 11/13.3, 500, uppercase, `text-tertiary` #8C8C82 |
| KPI 行 value | h2 22/26.6, 700, `text-primary` #1A1A1A，tabular-nums |
| KPI 行 delta | caption 12/14.5, 400，↑/↓ 配 `success-700` / `danger-700` |
| 分隔线 | 1 px `border-subtle` |
| 底部 caption | `text-tertiary` 12/14.5（"Targets · VAR ≥ 75% · Citation F1 ≥ 0.85 · P95 ≤ 20s · $ ≤ 0.10"） |

## §62 LLMRouterPicker · 模型路由

> 文件：`components/domain/settings/LLMRouterPicker.vue`
> 图：`062-03-am-llm-router-picker.png`

### 视觉
- 顶部预览条：`Local Qwen2.5-32B → Haiku 4.5 → Sonnet 4.6 ⌄`（mono 箭头，按 stage 顺序 plan→synth→judge）。
- 弹出面板：堆叠 3 行模型；每行 6-dot drag handle + 名字 + size chip（`32B` / `200B` / `400B`）+ 右侧 toggle 启用。
- 底部 `+ Add model` 虚框；右下 `Save` brand-500 / 左下 `Reset to global default` 链接。

### 模型卡内（展开模式）
- vendor 图标 + 名字（Anthropic / OpenAI / Local Ollama）。
- 元信息 chips：`200K ctx` / `$3 in / $15 out per 1M` / `p50 0.9s` / 标签 `good for: synth, judge`。
- 评级条：`Quality ★★★★☆ · Cost $$ · Latency ⚡⚡`。

### 状态
collapsed / expanded / drag-active / disabled-toggle / preset-picker（顶部 segmented `cheap / balanced / max-quality / custom`）。

### 交互
1. drag 改变 stage 顺序（plan / synth / judge 顺序即列表顺序）。
2. toggle 启用/停用某模型；至少 1 启用，否则 `Save` 禁用 + 红字提示。
3. `+ Add model` → 弹 Drawer：搜索 / 粘贴 endpoint / API key。
4. preset 切换 `cheap` 自动选 `Local + Haiku + Haiku`，`max-quality` 选 `Sonnet + Opus + Opus`，并显示估算 cost 差异。
5. Save → POST `/settings/router`；成功 toast；改变会引发 in-flight 任务 confirm（**第二次确认**）。

### A11y
- toggle 用 `role="switch"` + `aria-checked`。
- drag 备份键盘方案（聚焦 + Alt+↑/↓）。

### 动效
- 顺序变化 FLIP 240 ms；preset 切换数值滚动 360 ms。

### Vue 实现
- `<LLMRouterPicker v-model:rule="routerRule" :models :presets @save />`。
- store：`useSettingsStore.routerRule = { plan: 'local-qwen', synth: 'haiku-4.5', judge: 'sonnet-4.6' }`。
- 与 openapi schema 对齐：用 `vee-validate + zod` 校验最少 1 启用、stage 不重复。

### 联动
- 更换 model → CostMeter 立刻按新单价重算预算消耗速率预测。
- judge 改为 Local → AlertBanner info: "Judge model now local — eval scores may differ; baseline reset suggested"。

---

### UI 参数（来自 UI_PROMPTS §03-AM）

| 类别 | 值 |
|---|---|
| 触发 select 尺寸 | 272 × 32 |
| 触发文字 | body-sm 13/15.7, 600, `text-primary` #1A1A1A；形如 "Local Qwen2.5-32B → Haiku 4.5 → Sonnet 4.6 ▾"；→ 箭头可视化路由链 |
| Popover 尺寸 | 360 × 280 |
| Popover 圆角 / 阴影 | 14 / shadow-md |
| 行高（模型行） | 48 |
| 行内布局 | grip-vertical handle icon 20 左 + 模型名 body-sm 13/15.7, 600 + 模型 size pill + 末尾 toggle 移除 |
| 模型 size pill | meta 11/13.3, 500, `bg-subtle` #F4F4F1 / `text-secondary` #515151，radius 6 |
| vendor logo 尺寸 | — （本 PROMPT 未画 logo；如需用 20×20） |
| 三 stage（plan/synth/judge）分组 | 本 PROMPT 用列表 + 拖拽排序表达"链"，未显式按 stage 分块；建议加视觉子分组：每段 12 上下间距，组名 meta 11/13.3, uppercase |
| 多选 chip | — （本 PROMPT 为单链选择 + 排序，未含多选） |
| 价格行字号 mono | — （本 PROMPT 未列价格；如需 mono 13/20, 400, `text-secondary`） |
| "+ Add model" 行 | ghost row，`brand-600` #3B30D9 |
| 底部按钮 | Primary "Save" + ghost link "Reset to global default" |

## §63 EmbedderPicker · 嵌入器选择

> 文件：`components/domain/settings/EmbedderPicker.vue`
> 图：`063-03-an-embedder-picker.png`

### 视觉
- 标题 `Embedder` 13 px label。
- 收起态：`[icon] BGE-M3 · 4096 dim · local ⌄`。
- 展开列表（单选 radio）：
  - `BGE-M3` + `Recommended` brand pill + `local` 12 px + `4096 dim` + 右侧成本 `$` chip。
  - `Voyage-3` + api + 1024 dim + `$$`。
  - `OpenAI text-embedding-3-large` + api + 3072 dim + `$$$`。
- 每行 radio + 名 + meta + 成本 chip。

### 状态
collapsed / expanded / changing-confirm（modal）/ rebuilding（进度 banner + 估算完成时间）。

### 交互
1. 选不同 embedder → 弹 Modal：`Switching embedder requires rebuilding the index (estimated 6m for 62k chunks). All retrieval will be unavailable during rebuild. Type the library name to confirm.`（**危险操作必须二次确认**）。
2. 确认后 `POST /settings/embedder?rebuild=true` → 顶部 AlertBanner warning + sticky 进度条。
3. 行 hover → 显示 multilingual / 适用语言列表 tooltip。

### A11y
- `role="radiogroup"` + 各 radio `aria-label="BGE-M3, 4096 dimensions, local, recommended"`。

### 动效
- 展开 200 ms height + fade；rebuilding 顶条 indeterminate。

### Vue 实现
- `<EmbedderPicker v-model="embedder" :options @switch-confirmed />`。
- 警告 Modal 用 BaseModal + `danger` variant。

### 联动
- 切换中 → 全局拦截 retrieval-dependent 操作（Chat / Search / Reasoning）。
- 重建完成 → KPI 全部重新跑 → AlertBanner success "Index rebuilt · Re-run evaluation to refresh KPIs"。

---

### UI 参数（来自 UI_PROMPTS §03-AN）

| 类别 | 值 |
|---|---|
| 触发 select 尺寸 | 272 × 32 |
| 触发文字 | body-sm 13/15.7，形如 "BGE-M3 · 4096 dim · local ▾" |
| Popover 行类型 | radio row |
| 行 name | body-sm 13/15.7, 600 |
| 行 sub caption | caption 12/14.5, 400, `text-tertiary` #8C8C82 |
| 推荐 badge | "Recommended"，`brand-50` #EDF0FF bg / `brand-700` #2A1FAF text，radius 6，meta 11/13.3, 500 |
| 末尾 "$" cost pill | radius 999，`bg-subtle` #F4F4F1 / `text-secondary` #515151 |
| 警告 banner 高 | — （本 PROMPT 未画警告 banner；如切换 dim 不匹配现有 chunks 时，沿用 §58 AlertBanner warning 行高 40） |
| 选项示例 | BGE-M3（local, 4096） / Voyage-3（api, 1024） / OpenAI text-embedding-3-large（api, 3072） |

## §64 BudgetSettingsForm · 预算设置表单

> 文件：`components/domain/settings/BudgetSettingsForm.vue`
> 图：`064-03-ao-budget-settings-form.png`

### 视觉
- 卡片标题 `BUDGET · PER QUESTION` 11 px UPPER。
- 表单 5 行（label 左、数字输入 + 单位后缀 右）：
  - `Max retrieval steps` `8` `steps`。
  - `Max LLM calls` `12` `calls`。
  - `Tokens per question` `32,000` `tokens`（千分位）。
  - `Daily cost cap` `5.00` `$`。
  - `Per-question cost soft cap` `0.20` `$`。
- 输入 width 96 px 右对齐 mono。

### 状态
default / dirty（顶部出现 unsaved chip + 底部 Save 启用）/ invalid（红框 + 行内错误：`Daily cap must be > 0`）/ overrideable（如 lib-level 覆盖 global 时，行右侧显 `inherited from global` 12 px tertiary + reset 链接）/ admin-locked（输入 disabled + 锁图标）。

### 交互
1. 数字输入：Tab 跳行；Up/Down 步进（cost 默认 0.01、tokens 默认 1000）。
2. Daily cap 改变 → 实时显示预估天数耗尽时间（按近 7 天用量速率）。
3. 阈值 70% 黄、90% 红：在 CostMeter 同步。
4. Save → 多端 broadcast；in-flight 超额任务被中止前显 5 s grace toast。

### A11y
- 每输入 `aria-describedby` 关联帮助文字与错误。
- 错误聚焦：首个错误自动 focus。

### 动效
- 错误抖动 1 次 160 ms；保存 → Save 按钮 spinner → check。

### Vue 实现
- **vee-validate + zod**：
  ```ts
  const schema = z.object({
    max_retrieval_steps: z.number().int().min(1).max(50),
    max_llm_calls: z.number().int().min(1).max(100),
    tokens_per_question: z.number().int().min(500).max(200000),
    daily_cost_cap: z.number().positive().max(1000),
    per_question_soft_cap: z.number().positive().max(50),
  })
  ```
- schema 由 `openapi-typescript` 生成的 `paths['/settings/budget']` 反推保持一致。

### 联动
- 修改 → CostMeter 立即重算环；超 90% → AlertBanner danger 拦截 expensive actions（**budget 是硬墙**）。

---

### UI 参数（来自 UI_PROMPTS §03-AO）

| 类别 | 值 |
|---|---|
| 表单宽 | 448 |
| 行数 | 5 |
| 单行高 | 48 |
| 行布局 | label body-sm 13/15.7, 400, `text-primary` #1A1A1A 左 + 数字 input 96 × 32 右 + 单位后缀 |
| input 高 | 32 |
| input 圆角 | 10（沿用 base/input） |
| input 描边 | 1 px `border-default` #D3D3CE |
| 数字单位 hint | meta 11/13.3, 500, `text-tertiary` #8C8C82（"steps" / "calls" / "tokens" / "$"） |
| Section heading | meta 11/13.3, 500, uppercase, `text-tertiary`（"BUDGET · per question"） |
| 分隔线 | 1 px `border-subtle` #E4E4E0 |
| 阈值告警颜色（与 CostMeter 一致） | 70% `warning-500` #F59E0A / 90% `danger-500` #EE4444 |
| 默认值（示例） | Max retrieval steps `[8]` · Max LLM calls `[12]` · Tokens per question `[32,000]` · Daily cost cap `[$5.00]` · Per-question cost soft cap `[$0.20]` |

## §65 SchemaEditor · 实体/关系类型编辑

> 文件：`components/domain/settings/SchemaEditor.vue`
> 图：`065-03-ap-schema-editor.png`

### 视觉
- 全屏页（左侧导航 Schema Editor active），主区为深色 mono YAML 编辑器（实际线上推荐 **双面板 + JSON preview toggle**，比图中纯 YAML 更易用）。
- 顶部 breadcrumb / 文件名 `library.schema.yaml` + `Reset to template` 链接。
- 右上 `Validate`（次按钮）/ `Save` brand-500。
- 成功 toast：`Schema saved successfully · library.schema.yaml has been updated · 10:42:21 AM`。

### 推荐结构（双面板）
- 左：实体/关系类型列表（拖拽排序、删除带 reference count guard）。
- 右：编辑表单 — 名称 / 颜色（颜色选自 **colorblind-safe palette**，Okabe-Ito 8 色 + brand-500，用 `color-blind` lib 校验对比） / 描述 / 别名（chip 输入） / 例子（文本域）。
- 顶部 segmented `Visual | JSON | YAML`，三视图同步。

### 状态
default / dirty（unsaved chip）/ invalid（行内错误聚合到顶部 banner）/ validating（spinner）/ saved / template-replace-confirm（覆盖原有 schema 二次确认）/ delete-blocked（"This type is referenced by 3,141 entities — migrate first"）。

### 交互
1. 添加类型 → 弹 form；名字唯一性 backend 校验。
2. 删除类型 → 若 reference > 0：禁用删除 + 提示 `Migrate to another type` 流程。
3. 颜色选择 → 实时预览到右侧 mini KG sample（3 节点 demo）。
4. JSON 视图直接编辑 → 失焦后用 zod 校验 + 高亮错误行。

### A11y
- 编辑器使用 **Monaco** + 内置 ARIA。
- 颜色选择不只用色块：每色配名（`Burnt Orange` / `Vermillion`），按钮 `aria-label="Color: Burnt Orange"`。

### 动效
- 类型重排 FLIP 240 ms；保存成功 toast slide-down 220 ms。

### Vue 实现
- 编辑器：**`@guolao/vue-monaco-editor`**（Monaco 包装，体积可接受且自带 YAML/JSON LSP）。
- 颜色校验：`npm color-blind` + 自写 contrast 检查。
- `<SchemaEditor v-model:schema :readonly @validate @save />`。

### 联动
- 保存 → `colorStore.entityTypes` 单一源更新 → KGCanvas / PathVisualization / LibraryCard 圆点 5 ms 内重渲染（**单一源**铁律）。
- 删除类型 → 联动 SearchPage / RetrievalPanel 的 type filter 选项同步移除。

---

### UI 参数（来自 UI_PROMPTS §03-AP）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 696 × 384 |
| 圆角 | 14 |
| 编辑器 bg | #0F1118（深色，仅编辑器内部例外） |
| 描边 | 1 px `border-subtle` #E4E4E0 |
| 顶部 tab bar bg | `bg-subtle` #F4F4F1（亮色侧） |
| Tab | "library.schema.yaml" + ghost link "Reset to template" |
| 左列宽 | — （本 PROMPT 是单编辑器 Monaco-lite，不含双列；如需双面板，建议左侧 240，右侧剩余） |
| 右列宽 | — （同上） |
| 行号 gutter | `text-tertiary` mono 11/13.3 |
| 正文代码 | JetBrains Mono 13/20 |
| 语法主题 keys | #8D9FFF（`brand-300`） |
| 语法主题 strings | #10B881（`success-500`） |
| 语法主题 numbers | #F59E0A（`warning-500`） |
| 语法主题 comments | #515151（`text-secondary`） |
| 每项 padding | — （单编辑器内部按 Monaco 默认 18 行高） |
| color picker 尺寸 | — （本 PROMPT 不含 color picker；如需 KG 实体色映射，沿用 24 × 24 swatch + radius 6） |
| palette 圆点尺寸 | — （如需 12 × 12，沿用 EvidenceTimeline 节点 dot） |
| 删除 guard 文案 | — （本 PROMPT 不含；删除 entity_type 时按 §69（global）模式：DELETE Modal 二次输入类型名确认） |
| Footer | ghost "Validate" + Primary "Save" |
| Save 成功 toast | 24 高 `success-50` #EBFCF5，置顶 form |

## §66 FailedErrorPopover · 失败错误弹窗

> 文件：`components/domain/feedback/FailedErrorPopover.vue`
> 图：`066-03-aq-failed-error-popover.png`

### 视觉
- 弹窗 320 px，radius `card` 14、`bg-surface`、`border: danger-300`、`shadow-md`。
- 顶部 icon ⊘ danger + 标题 `Parse error` 16 px。
- 正文 13 px：`Nougat detected scanned image-only PDF. No text layer. Retry with MinerU OCR pipeline?`。
- 两按钮：`Dismiss`（次） / `Retry with MinerU` brand-500。
- 锚点：上方 `Failed` 红 chip（点击触发弹出）。

### 区别（Popover vs Modal）
| | Popover | Modal |
|---|---|---|
| 打断 | 否（不夺焦点） | 是 |
| 锚点 | 必须有锚 | 居中 |
| 多个 | 同时仅 1 个 | 同时仅 1 个 |
| 用途 | 单元素的轻量决策 | 全局重要决策 |

### 状态
hidden / open / retrying（spinner replace 主按钮）/ error-detail-expanded（折叠区显 stack trace mono）/ feedback-submitting。

### 交互
1. `Failed` chip click → 弹 popover；外部 click / Esc 关闭。
2. `Show details` 折叠展开 stack trace + `Copy error ID` + `Submit feedback`。
3. `Retry with MinerU` → 调换管线重跑 → 关闭 + toast 进度。
4. 复制错误 ID（mono 短哈希）→ 用于 Langfuse 跨查。

### A11y
- `role="dialog"` + `aria-modal="false"`（轻量）+ `aria-labelledby="popover-title"`。
- focus trap 软：仅在打开时聚焦首个按钮。

### 动效
- open 160 ms fade + scale 0.96→1；close 120 ms fade。

### Vue 实现
- 用 **`@vueuse/core` `useElementBounding` + `@floating-ui/vue`** 实现 popper；不引 naive-ui 的 NPopover 以保持轻量与可控性。
- `<FailedErrorPopover :anchor :error :stage @retry @feedback />`。

### 联动
- 失败任务 chip 来自 `taskStore.failed[]`；retry 调对应 stage 的 `/retry` 端点。
- 提交 feedback → 自动附 trace_id + 错误 ID → 进 FailureCaseTable 的 `human_reported` 集。

---

### UI 参数（来自 UI_PROMPTS §03-AQ）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 320 × 144 |
| 圆角 | 14 |
| 背景 | `bg-surface` #FFFFFF |
| 阴影 | shadow-lg（0 12 px 32 px rgba(15,15,20,.10)） |
| 描边 | 1 px `border-danger-500` #EE4444 at 20% alpha |
| padding | 16 |
| 锚定 | 失败 StatusPill 上方 |
| 阶段 chip | — （本 PROMPT 单错误源；如多阶段沿用 `danger-50` / `danger-700` chip body-sm 13/15.7） |
| 标题行 | body-sm 13/15.7, 600, `danger-700` #B91B1B + leading "⊘" glyph（"⊘ Parse error"） |
| message 字号 | body-sm 13/15.7, 400, `text-secondary` #515151，最多 3 行（PROMPT 用 body-sm 非 mono；mono 仅当含 stack/code 时） |
| stack trace 字号 | mono 13/20, 400（如需展开 stack） |
| 折叠箭头 | — （本 PROMPT 不含；如需 16 chevron-down，`text-tertiary`） |
| 底部按钮 | ghost "Dismiss" + Primary "↻ Retry with MinerU" |
| pointer 尺寸 | 8 × 8，底部中央 |

## §67 CostMeter · 成本计量

> 文件：`components/domain/settings/CostMeter.vue`
> 图：`067-03-ar-cost-meter.png`

### 视觉
两种形态：
- **顶栏 mini 版**（图中横条）：`Cost so far · $0.36 [▓▓▓▓░░░░░░] $0.36 / $5.00 daily cap` — 横向 progress、左侧绿字标签、中段填充 brand-500、右侧 mono 比值。
- **设置页大版**：环形 progress（外圈 8 px stroke、内圈数字 + 单位 + reset 时间 `resets in 14h 23m`）。

### 阈值色
- 0-70%：brand-500（健康）。
- 70-90%：warning（黄）。
- > 90%：danger（红 + 内呼吸动画 1.4 s loop）。

### 状态
under-budget / nearing（70-90）/ at-cap（≥ 90）/ exceeded（拦截模式：所有 expensive 操作禁用 + 顶部 sticky AlertBanner）。

### 交互
1. mini 版 hover → tooltip：今日明细（embed $0.01 / retrieval $0.04 / LLM $0.31 / re-rank $0.00）。
2. click → 跳 `/settings/budget`（即 BudgetSettingsForm）。
3. 颜色变红时 click 直达 `/settings/budget` 并 highlight `Daily cost cap` 行（**budget 是硬墙不是软提示**）。
4. 在 `exceeded` 状态下：Chat 发送 / Reasoning generate / Eval run 按钮 disabled + tooltip "Daily cap reached. Adjust budget or wait until reset."

### A11y
- `role="progressbar"` + `aria-valuenow / min / max`。
- 颜色 + 数字 + 文字三冗余；exceeded 时 `aria-live="assertive"`。

### 动效
- 数字滚动 120 ms；阈值跨越时整条 280 ms 渐染至新色 + 呼吸阴影 1 次。
- exceeded 红呼吸 1.4 s opacity 0.6 ↔ 1。

### Vue 实现
- mini 版纯 CSS bar；大版用 ECharts gauge（type='gauge'、半径 50%、tick 隐藏）或纯 SVG 圆环（推荐 SVG，省 90 KB）。
- `<CostMeter variant="'mini'|'ring'" :current :cap :resetAt />`。
- store `useCostStore` SSE 订阅 `/cost/stream`。

### 联动
- exceeded → 全局 danger Banner + 拦截 `chatStore.canSend = false` / `reasoningStore.canGenerate = false`。
- 改预算（§64） → 立即重算 ratio 与色阶。

---

### UI 参数（来自 UI_PROMPTS §03-AR）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 240 × 32（inline 行内） |
| 形态 | 非环形，水平进度条 + 标签（PROMPT 未画环形；如 Dashboard 需要环形版本，环外径 56 / 内径 40 — 冲突标注） |
| 左侧 label | meta 11/13.3, 500, uppercase, `text-tertiary` #8C8C82（"Cost so far"） |
| 中间数值 | mono 14/22, 600, `text-primary` #1A1A1A（"$0.36"） |
| 进度条尺寸 | 88 × 4 |
| 进度条圆角 | pill 999 |
| 进度条 fill 阈值色 | < 60% `brand-500` #4F46E4 ／ 60–90% `warning-500` #F59E0A ／ ≥ 90% `danger-500` #EE4444 |
| 右侧 caption | caption 12/14.5, 400, `text-tertiary`（"$0.36 / $5.00 daily cap"） |
| 中心数字字号（环形版本） | h2 22/26.6, 700, tabular-nums |
| 当前 / 上限字号（环形版本） | body-sm 13/15.7, 400, `text-secondary` |

---

## 附录 A · 4 severity 颜色对照表

> 应用于 §58 AlertBanner、§66 FailedErrorPopover、CostMeter 阈值色、所有 status chip / pill。color token 与 #HEX 双写。

| Severity | -50（bg） | -100 | -500（accent / icon） | -700（text） |
|---|---|---|---|---|
| info / citation | `info-50` #EBFDFF | `info-100` #CFFAFE | `info-500` #06B6D3 | `info-700` #0E7490 |
| success | `success-50` #EBFCF5 | `success-100` #D1FAE5 | `success-500` #10B881 | `success-700` #047856 |
| warning | `warning-50` #FFFAEB | `warning-100` #FEF3C7 | `warning-500` #F59E0A | `warning-700` #B45208 |
| danger | `danger-50` #FDF1F1 | `danger-100` #FEE2E2 | `danger-500` #EE4444 | `danger-700` #B91B1B |

> 备注：`-100` 阶在 PROMPT 中未显式给出（仅 50 / 500 / 700），此处按 Cobalt Lab token 体系常规色阶补齐，用于 chip secondary fill / hover；如与最终 token 表冲突以 token 表为准。

---

## 附录 B · KPI 阈值色规则表

> 应用于 §55 KPICard delta chip、§56 TrendBarChart target line、§61 QualityKPIPanel KPI 行、CostMeter 进度条 fill。

| 指标 | target | warning 阈值 | danger 阈值 | 同环比正向色 |
|---|---|---|---|---|
| VAR · Valid Answer Rate | ≥ 75% | < 80% （接近 target 但未达） | < 75% danger-500 | 上涨 `success-700` |
| Citation F1 | ≥ 0.85 | < 0.88 warning-500 | < 0.85 danger-500 | 上涨 `success-700` |
| P95 latency | ≤ 20 s | > 16 s warning-500 | > 20 s danger-500 | 下降 `success-700` |
| $ / question | ≤ $0.10 | > $0.08 warning-500 | > $0.10 danger-500 | 下降 `success-700` |
| Recall@10 | ≥ 0.70 | < 0.72 warning-500 | < 0.70 danger-500 | 上涨 `success-700` |
| Daily cost cap（CostMeter） | < 60% brand-500 | 60–90% warning-500 | ≥ 90% danger-500 | — |
| Per-question budget | < 70% brand-500 | 70–90% warning-500 | ≥ 90% danger-500 | — |

> 取色：positive delta = `success-50` bg + `success-700` text；negative delta = `danger-50` bg + `danger-700` text；方向箭头 ↑/↓ 一律 600 weight。

---

## ECharts vs Naive UI 数据展示取舍清单

| 场景 | 选 ECharts | 选 Naive UI | 理由 |
|---|---|---|---|
| 30 天趋势柱图 / 折线 | ✓ | ✗ | dataZoom / brush / markLine 原生支持；Naive 无柱图 |
| 单指标 sparkline（28 px 高） | ✓（共享实例池） | ✗ | Naive 无 sparkline；ECharts 关闭交互可压到 < 1 ms 渲染 |
| 进度条 / 单值 KPI | ✗ | ✓ NProgress / 自写 | ECharts gauge 太重（90 KB） |
| 表格（虚拟滚动 + 展开行） | ✗ | △ NDataTable | 推荐 **TanStack Table** > Naive，扩展性更强 |
| 时间轴 chips | ✓（custom series） | ✗ | vis-timeline 230 KB 不值；ECharts 复用现成 instance |
| 路径/图谱 | ✗ ECharts graph 不够直观 | ✗ | **cytoscape + dagre** 专业 |
| Drawer / Modal / Toast | ✗ | ✓ | Naive 现成够用 |
| 颜色选择 / 表单控件 | ✗ | ✓ + vee-validate | Naive 输入组件成熟 |
| 大数据散点（>10k 点） | ✓（GL renderer） | ✗ | WebGL 唯一选择 |

**裁决**：图表统一 ECharts 5 + vue-echarts；表单/Modal/Toast 用 Naive UI；表格用 TanStack Table；图谱用 cytoscape；时间用 date-fns。**不引** vis-timeline / chart.js / d3 完整版（仅按需引 `d3-scale` `d3-shape` 子包）。

---

## 三条铁律（禁止突破）

1. **所有数值必须显示阈值上下文**：KPI、CostMeter、TrendBarChart、HypothesisCard 评分——任何一个数字旁必须有 `target / cap / threshold`。孤立数字（如 `0.872`）禁止出现。
2. **危险操作必须二次确认**：Delete Library、Switch Embedder（重建索引）、Replace Schema、Refute Hypothesis、Change Router Rule（in-flight 任务受影响）、Bulk Re-train。要求 `Modal + 输入名匹配 / 按钮二态延时` 二选一，且 Modal 标题必含动词 + 不可逆描述。
3. **Budget 是硬墙不是软提示**：超 daily cap 后 Chat send / Reasoning generate / Eval run / Re-train 全部 disabled；仅 admin 在 `/settings/budget` 主动提额可解锁。CostMeter exceeded ≠ AlertBanner（Banner 是辅助），按钮 disabled 才是硬墙。
