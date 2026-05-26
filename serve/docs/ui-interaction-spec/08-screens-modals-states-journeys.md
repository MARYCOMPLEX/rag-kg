# 08 · Screens / Modals / Edge-States / Journeys — Composition Layer

> 本文件是 RAG-KG Copilot 前端规范的**整合层**。把 01–07 的 token / 原子 / 布局 / 域组件
> 编排成 **8 屏 × 4 Modal × 7 边界态 × 3 旅程** 的完整产品体验。
>
> 设计宪法：**URL = 状态**；**切库 = 路由跳转 + store reset**；**Library 是数据分区单位，绝不混淆**。
>
> 视图清单：
>
> | 编码 | 路由 | 图 | 状态机最小集 |
> |---|---|---|---|
> | S1 | `/onboarding` | 068 | empty(永远) → CTA |
> | S2 | `/libraries` | 069 | empty / loading / data |
> | S3 ★ | `/lib/:id/chat[/:sessionId]` | 070 | empty / streaming / data / partial-error / forbidden |
> | S4 | `/lib/:id/kg` | 071 | empty / building / data / too-large |
> | S5 | `/lib/:id/review[/:taskId]` | 072 | configure / running / paused / done / failed |
> | S5b | `/lib/:id/review` (no taskId) | 073 | configure |
> | S6 | `/lib/:id/docs[/:docId]` | 074 | empty / ingesting / data |
> | S7 | `/lib/:id/reason \| /hypothesize` | 075 | empty / running / data |
> | S8 | `/lib/:id/eval \| /settings` | 076 | data |
>
> Modal 清单：M1 LibraryCreate · M2 DeleteConfirm · M3 CommandPalette ⌘K · M4 DocumentDetailDrawer
> 边界态：A skeleton · B stream-break · C 0-hit evidence · D budget-exceeded · E worker-offline · F toast · G cross-library misroute
> 旅程：J1 首次答案 · J2 综述长任务 · J3 KG→Chat 闭环

---

## 第一部分 · 主屏 S1–S8 的 Layout 与交互编排

每屏统一 7 项规范：
1. **Layout（grid/flex + 断点）**
2. **状态机**
3. **URL / Query 反映哪些可分享状态**
4. **关键交互（鼠 / 键 / SSE）**
5. **跨组件 store 链**
6. **A11y landmark 分布**
7. **性能策略（lazy / suspense / code-split）**

通用 shell（所有 S2–S8 共享）：

```
+------------------------------------------------------------+
| TopBar (h:56)  Logo · Breadcrumb · ⌘K · LangSwitcher · Bell · CostMeter · Avatar |
+--------+---------------------------------------------------+
| SideNav |                                                  |
| 240px   |        <route view, role="main">                 |
| (mini   |                                                  |
| 64px)   |                                                  |
+--------+---------------------------------------------------+
```

- TopBar = `role="banner"`；SideNav = `role="navigation"`；route view = `role="main"`。
- TopBar 在 `<lg` 折叠为汉堡菜单；SideNav 切换为 Drawer（fixed, slide-in）。
- TopBar 上的 LibrarySwitcher 触发 **router.push 而不是 store.setLibraryId**（URL 是唯一真值）。

---

### S1 · Onboarding（图 068）

#### 1. Layout
- 单列 centered，max-width 720px，垂直居中。
- 三张水平 Card，等宽，gap 24px；移动端纵向堆叠。
- 顶部 logo + 副标题（"Your research, privately augmented."），底部主 CTA `Create your first library` 占满宽度。

#### 2. 状态机
- 永远 `empty`，不依赖远端数据。
- 仅本地 `onboardingStore.dismissed` 决定再次访问是否跳过。

#### 3. URL
- 不接 query；用户主动 `?from=settings` 可强制再次访问（设置页 "Show onboarding again"）。

#### 4. 关键交互
- 三张 Card 是 **passive 介绍**（无 click）。
- 主 CTA：Enter / Space → 触发 `openModal('library-create')`。
- Esc 不可关闭（因为没有可关的层）。
- 右上角 `Skip` 文本按钮：`dismissOnboarding()` + `router.replace('/libraries')`。

#### 5. store 链
```
onboardingStore.markStarted()
  → 监听 libraryStore.created (一次性)
  → onboardingStore.markCompleted() + router.push(/lib/:newId/docs)
```

#### 6. A11y
- `<header>`（logo / lang switcher）+ `<main aria-labelledby="onboarding-title">`。
- 首焦点：主 CTA 按钮（`autofocus` 等效，使用 `useFocusOnMount`）。
- 卡片标题用 `<h2>`，组成 doc-outline。

#### 7. 性能
- 路由级 code-split：`() => import('@/screens/Onboarding.vue')`。
- 资源极轻：3 张 inline SVG，无第三方依赖。
- 预 prefetch `LibraryCreateModal`（用户极可能点 CTA）。

#### 8. UI 参数（来自 UI_PROMPTS §S1）
| 类别 | 值 |
|---|---|
| Canvas | 1440×900 / bg-canvas #FAFAF9（无 SideNav） |
| Hero 单列 max-w | 720 |
| 垂直节奏 | 24 |
| 顶左 logo squircle | 40×40 / brand-500 / 字 "◆" + gap 8 + "RAG-KG Copilot" body 14 700 |
| Hero title | display 36/43.6 700 text-primary（单行） |
| Subtitle | body-lg 16/22 text-secondary（2 行） |
| 3 张 Step Card | 240×200 / radius 14 / bg-surface / 1px border-subtle #E4E4E0 / padding 24 / 卡间 gap 32 |
| Step 序号 | display 28 700 brand-500 #4F46E4 |
| Step 标题 | h4 18 600 |
| Step 描述 | body-sm text-secondary |
| Primary CTA | 280×52 / radius 10 / bg brand-500 / text white / body-lg 600 |
| Secondary ghost CTA | body-sm 600 brand-600 |
| 背景 | 极淡 dot-grid（3% 透明度，bg-muted #EAEAE5），禁用渐变/图片 |
| 动效 | hero fade-in 240ms / cards stagger 80ms / CTA mount 1× subtle pulse |
| 关键操作位置 | 中心垂直略上偏，CTA 位于 hero/subtitle/cards 之下 |
| 断点 <lg | — |

---

### S2 · Library Dashboard（图 069）

#### 1. Layout
12 列 grid，gap 24px：
```
[ Welcome banner (col 1-12, h auto) ]
[ KPI strip: 4× KpiCard (col 1-3 each) ]
[ Recent chats (col 1-6) ][ Ingestion & tasks (col 7-12) ]
[ KG snapshot (col 1-6) ][ Top entities (col 7-12) ]
[ Recently added documents (col 1-12) ]
```
断点：
- `md`：变 2 列（KPI 各占 50%）。
- `sm`：单列堆叠；KPI strip 横向 swipe。

#### 2. 状态机
- `loading` → 全块 Skeleton（`<lib-dashboard-skeleton>`，结构同构）。
- `empty`（库为空）→ EmptyState + "Upload your first document" CTA → `/lib/:id/docs`。
- `data` → 上述 grid。
- `partial-error`（某个 widget 失败）→ 该格 inline AlertBanner + "Retry"，不影响其他格。

#### 3. URL
- `/libraries`：库列表卡片。
- `/lib/:id`：该库的 dashboard。
- query：`?tab=recent | tasks | kg`（深链到某个 widget tab）。

#### 4. 关键交互
- Library Card → `router.push(/lib/:id)`。
- 任一 widget 卡片右上 `View all` → 子页面。
- ⌘K 任意时刻打开 CommandPalette。
- 数字 1–6 在该屏被忽略（避免和 SideNav 冲突）。

#### 5. store 链
```
libraryStore.list()  →  load cards
  on enter /lib/:id  →  libraryStore.setActive(:id) → reset chatStore/kgStore/evidenceStore
                     → parallel: recentChatsStore / ingestionTaskStore / kgSnapshotStore
```

#### 6. A11y
- `<main>` 包多个 `<section aria-labelledby>`。
- KPI 数字使用 `aria-label="Chunks: 98,104"`（屏读完整词，不读千分位逗号）。

#### 7. 性能
- Recent chats / KG snapshot 各自 `<Suspense>` 包裹，避免一个慢源拖垮全屏。
- KG snapshot 用静态 PNG 缩略图 + lazy hydrate（点击放大才加载 force-layout）。
- KPI 用 stale-while-revalidate 缓存（5 min）。

#### 8. UI 参数（来自 UI_PROMPTS §S2）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar 1440×56 / 无 SideNav |
| 容器 max-w | 1440（全局 dashboard 无 SideNav，主区直占满） |
| 主区 padding | 32 |
| Page title | h1 28/33.9 700 + 右上 Primary "+ New Library" 144×40 brand-500 |
| Page meta | body-sm text-tertiary（一行汇总数字） |
| Library grid | 4 列 / gap 20 / 卡片来自 03-AJ |
| 中段 divider | 1px / 上下各留白 32 |
| 双栏区域比例 | 左 896w · 右 384w（16:9 拆分） |
| Recent activity 卡 | bg-surface / radius 14 / 1px border-subtle / padding 24 / 内分隔 1px subtle |
| QualityKPI 卡 | 来自 03-AL（右侧 384w） |
| Sticky footer-bar | 1376×40（在内容区内）；状态 legend 22h pill |
| 阴影策略 | 卡片 shadow-sm；hover 才升 shadow-md |
| 关键操作位置 | 标题行右上 CTA "+ New Library" |
| 断点 <lg | — |

---

### S3 · Chat / Q&A ★ 旗舰（图 070）— 详写

#### 1. Layout — 三栏 grid（桌面优先）
```css
.chat-shell {
  display: grid;
  grid-template-columns: 260px 1fr 440px;  /* Sessions | Conversation | Evidence */
  grid-template-rows: 1fr auto;            /* main | composer */
  grid-template-areas:
    "sessions conversation evidence"
    "sessions composer      evidence";
  height: calc(100vh - 56px);              /* 减 TopBar */
  gap: 0;
}
```
- 默认 EvidencePanel **折叠**（44px 竖条 + 图标），让 Composer 主区更宽：
  - 折叠态：`grid-template-columns: 260px 1fr 44px`。
  - 展开状态保存在 `chatLayoutStore.evidenceOpen`（localStorage）。
- 断点：
  - `<xl(1440px)`：默认折叠 SessionList（变 56px mini）+ EvidencePanel 仍展开。
  - `<lg(1024px)`：单列 + 顶部 Tabs：`Conversation | Evidence | Sessions`。
  - 手机：fixed bottom Composer + sliding sheet for Evidence。

#### 2. 状态机
| 状态 | 触发 | UI 表现 |
|---|---|---|
| `empty` | 新 session，无消息 | 居中 EmptyState + 3 个 sample-question Chips |
| `streaming` | SSE 进行中 | assistant 气泡内 token 逐字 + 灰色光标；Composer disabled，显示 "Stop" 按钮 |
| `data` | SSE 完成 | 完整答案 + CitationChip 数组 + 反馈按钮（👍/👎/复制） |
| `partial-error` | stream 中断 | 保留已输出 token + 红色 inline chip "Stream interrupted · Retry / Continue from here" |
| `forbidden` | session 不属于当前库 | 全屏 ErrorBoundary "This session belongs to another library" + 跳回按钮 |

#### 3. URL / Query
- `/lib/:id/chat`：新建空 session（不持久化直到首发消息）。
- `/lib/:id/chat/:sessionId`：恢复 session。
- query：
  - `?deep=1`（开启深度模式 = reasoning trace + path viz）
  - `?model=gpt4o`（覆盖默认路由器选择，仅本次 session）
  - `?prefill=...`（KG → Chat 跳转时预填 composer 草稿）

#### 4. 关键交互 — 鼠 / 键 / SSE 三流

**键盘 map（chat scope）**
| 键 | 行为 |
|---|---|
| `⌘K / Ctrl+K` | 打开 CommandPalette（全局） |
| `/` | 聚焦 Composer 并插入 `/` 触发命令模式 |
| `Esc` | 若 streaming → 停止；否则失焦 Composer |
| `⌘Enter / Ctrl+Enter` | 发送 |
| `Shift+Enter` | Composer 换行 |
| `⌘↑` | 编辑上一条用户消息 |
| `⌘[` | 折叠 / 展开 SessionList |
| `⌘]` | 折叠 / 展开 EvidencePanel |
| `⌘.` | 切换深度模式（同步 URL `?deep=`） |
| `J / K` | 在 message list 内上下定位（不在 composer 聚焦时） |
| `C` | 复制当前选中 assistant 答案为 Markdown |

**SSE 事件流（`useSSEChat` composable）**
```
event: token   data: {"delta":"...","msgId":"m_1"}
event: citation data: {"chunkId":"c_88","msgId":"m_1","index":3}
event: trace   data: {"step":"retrieve","status":"done","duration":312}  // 仅 deep=1
event: done    data: {"msgId":"m_1","usage":{...}}
event: error   data: {"code":"BUDGET_EXCEEDED","retryable":false}
```
- `token` 增量 push 到 `chatStore.messages[id].content`。
- `citation` push 到 `evidenceStore.byMessage[msgId]` —— **EvidencePanel 实时填充**，鼠标 hover citation chip 时高亮对应卡片。
- `trace` push 到 `reasoningTraceStore` —— 折叠面板显示步骤树。
- `error` 转 toast + 把当前 msg 状态置为 `partial-error`，但 **不清空已输出 token**。

#### 5. 跨组件 store 链
```
Composer.submit()
  → composerStore.draft = ''  (clear immediately, optimistic)
  → chatStore.appendUserMsg(text)
  → chatStore.appendAssistantPlaceholder(msgId)
  → useSSEChat.start({sessionId, libraryId, deep, model})
     ↳ token   → chatStore.patchAssistant(msgId, delta)
     ↳ citation→ evidenceStore.add(msgId, chunkId)
     ↳ trace   → reasoningStore.push(step)
     ↳ done    → chatStore.finalize(msgId); costStore.add(usage); notificationStore.maybePulse()
     ↳ error   → chatStore.markPartialError(msgId, err)

EvidencePanel ←watches→ evidenceStore.byMessage[chatStore.focusedMsgId]
CitationChip.click → evidenceStore.scrollTo(chunkId) + 高亮 600ms
"Discuss in chat" from KG → composerStore.prefill(text) + router.push
```

#### 6. A11y
- `<aside aria-label="Sessions">` 左栏；`<main aria-label="Conversation">` 中栏；`<aside aria-label="Evidence">` 右栏。
- assistant 消息加 `role="region" aria-live="polite"`，token 流追加时**不要**每个字都触发 aria-live（性能爆炸），用节流：每 250ms 让 screen reader 读一次新内容。
- CitationChip 必须有 `aria-describedby="ev-card-:id"`（链到 EvidenceCard 的 id）。
- streaming 时给 Composer `aria-busy="true"`。
- 焦点策略：发送后焦点 stays in Composer（方便连发）；用户按 `⌘↑` 时焦点跳到上条用户消息（可编辑）。

#### 7. 性能策略
- 路由级 code-split：`Chat.vue` 单独 chunk（含 markdown 渲染器、citation chip、reasoning trace）。
- Composer 内的 markdown / code-highlight 用 `markdown-it` + 异步 import `shiki`（懒）。
- 长 session（>200 messages）：虚拟列表（`vue-virtual-scroller`），但 streaming 消息不进虚拟池（避免 jitter）。
- EvidencePanel 卡片 lazy load 内容预览（intersection observer）。
- SSE 用 `fetch` + `ReadableStream`（不要用 EventSource — EventSource 不能带 Authorization header）。
- token 节流：进店速度太快时（>50 tokens/s）batch 渲染（rAF 合并），避免 layout thrash。

#### 8. UI 参数（来自 UI_PROMPTS §S3）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar 1440×56 / SideNav 240（"◆ Chat" 激活） |
| 三栏 grid 列宽 | SideNav 240 / Conversation 760（=1440-240-440）/ EvidencePanel 440 |
| 容器 max-w | 1440（全宽 chrome） |
| Conversation padding | 32 |
| 会话标题 | h2 22/26.6 700 text-primary（单行） |
| 标题下 divider | 1px border-subtle / 宽 680 |
| 消息间 gap | 24 |
| User Avatar | 28 brand-tinted；Assistant Avatar 28 brand-500 "◆" |
| 消息正文 | body 14/22 text-primary |
| Citation chip | INFO cyan（非 brand 蓝） |
| Streaming caret | 22ms/token · 1.0Hz 闪烁 |
| Composer | 712w × 112h（min）/ 黏底 / 来自 03-N |
| EvidencePanel header | h3 "Evidence" + caption "3 sources cited · click [n] in answer to jump" |
| EvidenceCard | 392×196 / 3 张堆叠 / 第一张当前激活态高亮 |
| 0-hit EmptyState | 替换右栏，396w |
| 阴影策略 | 仅 Composer 用 shadow-md；其它保持 ink-like |
| 关键操作位置 | Composer 位于中栏底部右侧栏沟槽 |
| 断点 <lg | 折成 Tabs（Conversation / Evidence / Sessions）— 未写细则，标 — |

---

### S4 · KG Browser（图 071）

#### 1. Layout
```
+----------------+---------------------+----------------+
| FilterPanel    |   KG Canvas         | EntityDetail   |
| 280px          |   1fr               | 360px (drawer) |
| (collapsible)  |   (sigma/cytoscape) | (right-side)   |
+----------------+---------------------+----------------+
| Footer mini-map (h:120)  · Path-trace timeline       |
+------------------------------------------------------+
```
- KG Canvas 默认 full-bleed；Filter / Detail 通过 `⌘[` `⌘]` 折叠。
- `<md`：FilterPanel 改为顶部 Sheet。

#### 2. 状态机
- `empty`（图为 0 节点）：EmptyState "No entities yet — ingest documents first" + 跳 `/docs`。
- `building`（KG 任务运行中）：覆盖层进度条 + "Building knowledge graph... 1,243 / 8,000 chunks"。
- `data`：交互式画布。
- `too-large`（>5k 节点）：默认仅显示 top-200 by degree + Banner "Showing 200 of 8,341 entities. Apply filter to see more."

#### 3. URL
- `/lib/:id/kg?focus=e_88&hop=2&type=Method,Dataset&search=community`
- focused entity / hop depth / type filter / search 全部进 URL，可分享。

#### 4. 关键交互
- 节点 click → EntityDetailDrawer + `?focus=e_88`。
- 节点 right-click → 上下文菜单：`Expand neighbors`, `Find paths to...`, `Discuss in chat`, `Pin`, `Hide`。
- 拖拽节点：local 重定位（不持久化），双击节点：fit-to-view。
- `+ / -` 缩放，`F` fit-all，`Esc` 取消选择。
- "Find paths to..." → 弹 entity picker → 跳 `/reason?from=e_88&to=e_99`。

#### 5. store 链
```
kgStore.loadGraph(filters)
  → cache by (libraryId, filterHash)
focusEntity(id) → kgStore.focusedId = id + entityDetailStore.fetch(id)
  → 同时 evidenceStore.loadForEntity(id) (右抽屉显示证据 chunks)
"Discuss in chat" → composerStore.prefill("Tell me about entity [name]") + router.push(/lib/:id/chat)
```

#### 6. A11y
- KG canvas 是 WebGL，对屏读不可见 — 提供 **"Entity list view" 切换**（同数据的纯 HTML 列表），URL `?view=list`。
- FilterPanel 是 `<aside aria-label="Filters">`。
- 选中节点时 `aria-live` 通报 "Selected entity: GraphRAG — type Method — 47 mentions"。

#### 7. 性能
- canvas 引擎：`sigma.js`（百万节点级）或 `cytoscape.js`（更易用，<10k 节点）—— 默认 cytoscape，>5k 时切 sigma。
- 节点纹理 atlas + LOD（缩远时只画圆点）。
- filter 走 web worker（避免主线程卡顿）。
- entity detail drawer lazy load，evidence 列表分页。

#### 8. UI 参数（来自 UI_PROMPTS §S4）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar / SideNav 240（"◇ Knowledge Graph" 激活） |
| 四列 grid 列宽 | SideNav 240 / FilterPanel 280 / KGCanvas 560 / EntityDetailDrawer 360 |
| 容器 max-w | 1440 |
| Canvas 背景 | 12% bg-muted dot-grid |
| 中心节点选中态 | 2px brand-500 ring + brand-50 inner glow + shadow-md |
| Canvas 工具栏 | 右上 4 个 icon button（fit / reset / export-png / export-json）+ tooltip |
| Footer legend strip | 24h，6 个颜色 dot + 类型名；左 caption "8,491 entities (top 50 shown)"，右 "31,219 triples · confidence ≥ 0.65" |
| KG 节点 settle | 320ms spring |
| Empty state | 替换 canvas："No entities match the current filters. Try lowering confidence to 0.5 or selecting more types." |
| 关键操作位置 | Canvas 顶右 toolbar；List view toggle 也在 toolbar |
| 断点 <lg | FilterPanel 折成顶部 Sheet（与文档第 1 节一致）；右抽屉折叠 |

---

### S5 · Review Generation In Progress（图 072）

#### 1. Layout
```
+----------+-----------------------------------+-------------+
| Pipeline | DraftStream (markdown live)       | LiveCit.    |
| Tree     | 1fr                               | List 280px  |
| 320px    |                                   |             |
+----------+-----------------------------------+-------------+
| RunStats Sidebar (footer band, h:96)                       |
+------------------------------------------------------------+
```
- 三栏 + 底部 stats band。
- "Run in bg" 按钮把整个 task 折叠到右下 mini-pill，主区返回 S5b 配置态（用户可启新任务）。

#### 2. 状态机
- `configure`（即 S5b）→ `running` → `paused`（用户主动）/ `failed`（worker 报错）/ `done`。
- `partial`：某 subsection 失败但其他 ok → 在 PipelineTree 该节点变红，整体仍 `running`，最后变 `done-with-warnings`。

#### 3. URL
- `/lib/:id/review` = S5b configure。
- `/lib/:id/review/:taskId` = S5 in-progress / done view。
- query：`?section=4`（跳到第 4 章草稿位置）。

#### 4. 关键交互
- "Cancel run" → 二次确认 → `taskStore.cancel(taskId)`，已生成章节保留。
- "Run in background" → 不改 URL，仅 minimize 到全局右下 floating mini-progress；点击 mini 又能弹回。
- DraftStream 内的 chunk 引用 → 右栏 LiveCitationList 滚动到对应卡片。
- 章节侧边 hover → 显示 "Regenerate this section" 按钮（局部重跑）。

#### 5. store 链
```
taskStore.create({type:'review', config}) → taskId
  → router.push(/review/:taskId)
useTaskStream(taskId) (SSE)
  ↳ pipeline-step → pipelineStore.patch(stepId, status)
  ↳ draft-token  → reviewStore.appendChunk(sectionId, delta)
  ↳ citation     → evidenceStore.addForTask(taskId, chunkId)
  ↳ stats        → runStatsStore.update({elapsed, cost, tokens})
  ↳ done         → notificationStore.push('Review ready', taskId)
"Run in bg" → taskStore.minimize(taskId) → floatingTaskBar 显示
```

#### 6. A11y
- DraftStream 是 `<article aria-live="polite">`，节流和 S3 同。
- PipelineTree 是 `<nav aria-label="Pipeline steps">`，每个 step 用 `aria-current="step"`。

#### 7. 性能
- DraftStream 用增量 markdown 渲染（差量解析最近 N 行）。
- 长草稿（>10k tokens）：折叠已完成章节，渲染时虚拟化。
- PipelineTree 用纯 CSS 动画，不用 framer-motion（避免占用主线程）。

#### 8. UI 参数（来自 UI_PROMPTS §S5）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar 含 "Review · GraphRAG advances 2024–2025" / SideNav "◇ Review generation" 激活 |
| 三列 grid 列宽 | PipelineTree 320 / DraftStreaming 688 / LiveCitationList 336 |
| 列高 | 784（每列） |
| 列间 gap | 24 |
| 主区 padding | 24 |
| 容器 max-w | 1440 |
| Header 右上 StatusPill | "● Running" + "Run in bg ↗" body-sm 600 brand-600 |
| Pipeline tree 步骤 | 7 阶段，含 token 与 ETA |
| RunStats 块 | Tokens 14,328 / 32,000 · Cost $0.36 · Elapsed 04:18 · ETA ~03:30 |
| Footer 按钮 | Secondary "Cancel run" 130×40 / Primary "↓ Download draft .md" 142×40（完成前禁用） |
| 新增 citation 高亮 | brand-50 持续 800ms |
| 关键操作位置 | 顶右 "Run in bg ↗"；底部左栏 Cancel/Download |
| 断点 <lg | — |

---

### S5b · Review Configuration（图 073）

#### 1. Layout
单列 form, max-width 720px, 居中。分组：
- Topic（input）
- Sections template（chips：默认 / Survey / Method comparison / Custom）
- Depth（slider 1-5）
- Reranker（select）
- Model（LLMRouterPicker）
- Budget（BudgetSettingsForm 子集，inline）
- Estimated cost preview（右上 sticky pill）

#### 2. 状态机
- `configure`（默认）/ `validating`（提交时）/ `error`。

#### 3. URL
`/lib/:id/review?topic=...&template=survey&depth=3`（草稿态可分享）。

#### 4. 交互
- Submit → 创建 task → 跳 `/review/:taskId`。
- "Save as preset" → 写 settingsStore。
- 实时 cost 预估（debounce 500ms）。

#### 5-7. 同其他表单页，略。

#### 8. UI 参数（来自 UI_PROMPTS §S5b）
| 类别 | 值 |
|---|---|
| 主卡 | 720×620 / radius 20 / bg-surface / shadow-md / padding 40 / 居中 |
| 标题 | h2 "Generate a literature review" + body-sm text-secondary 副标题 |
| Topic Textarea | 640×96 |
| Year range | BaseSlider 双滑块（2018 ↔ 2025），value chip "2024–2025" |
| Target length | 3 段 segmented "1,500 / 3,000 / 5,000 words"（默认中间） |
| Citation style | segmented "Numbered [1] / Author-year (Edge 2024)" |
| Subtopics chips | 可移除，示例 "Pre-trained models" "Hierarchical KG" |
| Cost row | "Estimate cost" 按钮 + 结果 body-sm "≈ 21,500 tokens · ~$0.42 · ~6 min" |
| Footer | Secondary "Cancel" + Primary "Run review →" 156×44 brand-500 |
| 关键操作位置 | 卡底 "Run review →" |

---

### S6 · Documents（图 074）

#### 1. Layout
```
+------------------------------+
| DropZone (h:160, 默认折叠为 56) |
+------------------------------+
| Toolbar: search · filter · bulk actions |
+------------------------------+
| Documents Table              |
| (DocumentRow × N)            |
+------------------------------+
```
- 点击行 → 右侧推出 **M4 DocumentDetailDrawer**。

#### 2. 状态机
`empty / ingesting / data / mixed`（部分成功部分失败）。

#### 3. URL
- `/lib/:id/docs`：表格。
- `/lib/:id/docs/:docId`：表格 + Drawer 打开。
- query：`?status=failed&sort=size:desc&search=...&page=2`。

#### 4. 交互
- Drag & Drop 任意位置 → DropZone 亮起 + 自动 upload。
- 多选 checkbox → bulk actions: Delete / Re-ingest / Move to library。
- 行右键 → context menu。

#### 5. store 链
```
docsStore.list(libraryId, query)
ingestStream → docsStore.patchRow(docId, progress)
openDrawer(docId) → docDetailStore.fetch(docId) + chunksStore.fetch
```

#### 6. A11y
- 表格用 `<table>` 真表头 + `scope="col/row"`。
- DropZone 同时支持点击：`<button>` 触发 `<input type="file">`。

#### 7. 性能
- 表格虚拟化（>200 行）。
- 上传走分片（>50MB），并发上限 3。
- ingest 进度 SSE 单连接多任务复用。

#### 8. UI 参数（来自 UI_PROMPTS §S6）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar / SideNav "◇ Documents" 激活 |
| 容器 max-w | 1440 |
| 主区 padding | 32 |
| 主区 gap | 24 |
| Page header | h1 28/33.9 700 "Documents" + caption text-tertiary 汇总；右侧 "↑ Upload PDFs" 168×44 brand-500 |
| DropZone | 1376×120（来自 03-U） |
| 表格容器 | 1376×524 / radius 14 / bg-surface / 1px border-subtle |
| 表头行 | 48h / bg bg-subtle（列：TITLE / YEAR / STATUS / CHUNKS / ENTITIES / INGESTED） |
| 行分隔 | 1px bottom border-subtle |
| 表后 caption | "… 2,179 more docs"（text-tertiary 居中） |
| Sticky bottom 队列条 | 1376×40 / 左 "Queue · 14 indexing · 3 parsing · 1 failed" / 右 Cost meter chip "Today $0.36 / $5.00 daily cap" |
| FailedErrorPopover | 锚定失败行的 status pill 上方（来自 03-AQ） |
| 关键操作位置 | 右上 "↑ Upload PDFs" |
| 断点 <lg | — |

---

### S7 · Cross-Paper Reasoning / Hypothesize（图 075）

#### 1. Layout
左 Path Visualization（`PathVisualization` 组件）+ 右 EvidenceTimeline + HypothesisCard 列表。

#### 2. 状态机
`empty / configuring / running / data / failed`.

#### 3. URL
- `/lib/:id/reason?from=e_88&to=e_99&maxHop=4`
- `/lib/:id/hypothesize?seed=e_88&k=5`

#### 4. 交互
- 路径上点 chunk → 弹 EvidenceCard popover。
- "Discuss in chat" 按钮 → composerStore.prefill(描述 path) → 跳 chat。
- 假设卡 thumbs up/down → 写入 hypothesisStore（影响后续 ranking）。

#### 5. store 链
```
reasonStore.run({from,to,maxHop})
  ↳ SSE path-found → 实时追加路径
  ↳ done → ranking
```

#### 6-7. 同 S5。

#### 8. UI 参数（来自 UI_PROMPTS §S7）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 视口（长滚动）/ TopBar / SideNav "◇ Cross-paper reasoning" 激活 |
| 容器 max-w | 1440；prose 块 max-w 720；path canvas max-w 1024 |
| 主区 padding | 32 |
| Section 1 Question card | 672×88 / radius 14 / bg-surface / 1px border-subtle / padding 20 |
| Find paths CTA | "Find paths →" 144×36 brand-500（卡 footer 右） |
| PathVisualization | 672×320（来自 03-AC） |
| EvidenceTimeline | 672×252（来自 03-AD） |
| Hypothesize 入力フィールド | 各 320×52 / radius 14 / bg-surface / 1px border-default / padding 12 |
| HypothesisCard 全卡 | 656×180（带 3 meter bars） |
| HypothesisCard 紧凑 | 656×88 |
| Footer caption | body-sm text-tertiary "+ 2 more · Save shortlist · Export as JSON" |
| Empty state | "No path connects the two entities at depth ≤ 3 — try increasing depth, or relaxing confidence." |
| 关键操作位置 | 各 section 的 "Find paths →" / hypothesize 输入区下的 HypothesisCard |
| 断点 <lg | — |

---

### S8 · Eval / Settings（图 076）

#### 1. Layout
Tabs：Eval Dashboard | Models | Embedders | Budget | Schema | About。

#### 2. 状态机
`data`（绝大部分情况都有数据，settings 永远 readable）。

#### 3. URL
`/lib/:id/eval` 与 `/lib/:id/settings?tab=models`，**Eval 是 library 级，Settings 既有 library 级也有 global**（`/settings` 不带 lib id = global account/billing/keys）。

#### 4. 交互
- 任何 settings 改动 → "Unsaved changes" sticky banner + 离开页二次确认（unsavedChangesGuard）。
- LLMRouterPicker / EmbedderPicker / BudgetSettingsForm / SchemaEditor 各自独立 form，独立 save。

#### 5-7. 略。

#### 8. UI 参数（来自 UI_PROMPTS §S8）
| 类别 | 值 |
|---|---|
| Canvas / chrome | 1440×900 / TopBar / SideNav "◇ Evaluation" 激活 |
| 容器 max-w | 1440 |
| 主区 padding | 32 / gap 24 |
| Header | h1 "Evaluation dashboard" + 右上 LibraryFilter（268×36 select） |
| Subtitle | body-sm text-tertiary "smoke (10) · multihop (32) · review (5) · last 30 days" |
| AlertBanner | success 全宽（粘在 subtitle 下） |
| KPI row | 4 张 KPICard（来自 03-AF），总宽 1376w / gap 16 |
| Charts row 比例 | 64 / 36 |
| TrendBarChart | 864×280（左） |
| Library settings 卡 | 496×552（右；radius 14 / bg-surface / 1px border-subtle / padding 24） |
| 分节 | MODELS（LLMRouterPicker / EmbedderPicker） / BUDGET（5 数字字段） / DATA |
| Export button | Secondary 216×36 "↓ Export Library…" |
| Purge button | Danger ghost 216×36 "⊗ Purge Library (irreversible)" |
| FailureCaseTable | 864×248（左栏 chart 下方） |
| 关键操作位置 | 右上 LibraryFilter；Library settings 卡内 Purge |
| 断点 <lg | — |

---

## 第二部分 · 4 个 Modal/Overlay 体验细节

通用 modal 规则：
- ESC 关闭（除非有 unsaved changes，则二次确认）。
- 点击 overlay 关闭（**M2 Delete 例外** — 防止误关）。
- 首焦点 = 第一个非 disabled 输入框 / primary action。
- 关闭后焦点回到触发按钮（`useFocusReturn`）。
- modal 内部 Tab 循环（focus trap），用 `focus-trap` 或自实现。

---

### M1 · LibraryCreateModal（图 077）

**视觉**：宽 520px，高自适应；标题 "Create new library"；表单 + 底部双按钮。

**字段**
| 字段 | 类型 | 校验 |
|---|---|---|
| Name | text | 必填，2–60 字 |
| Slug | text（auto） | 从 Name slugify（kebab-case，去除 emoji 与非 ASCII），用户可改；**异步唯一校验**（debounce 400ms，调 `HEAD /v1/libraries/:slug`） |
| Description | textarea | 可选，<=240 |
| Primary language | select | en / zh / ja / multi（影响 embedder 默认） |
| Template | radio cards × 4 | `Empty` / `Survey writer` / `Code research` / `Personal knowledge` |

**交互**
- Name 输入 → 100ms debounce → 写 slug（如果用户未手动改过 slug）。
- Slug 唯一校验：右侧实时 status icon（spinner / check / cross）。
- 选 template → 右侧预览面板列出该模板自动启用的 settings（embedder / chunker / sample prompts）。
- Submit：
  1. 前端校验全过 → 按钮 loading
  2. POST `/v1/libraries` → 200
  3. toast `Library "GraphRAG Survey" created` + `View →`
  4. close modal
  5. `router.push('/lib/:newId/docs')`
  6. DocumentsScreen 自动高亮 DropZone（`?onboarding=1` query 触发 pulse 动画）
- 失败：inline error 在错误字段下；保留用户输入；不关闭 modal。

**A11y**
- `role="dialog" aria-modal="true" aria-labelledby="m1-title"`。
- 首焦点 Name 输入。
- 异步唯一校验结果用 `aria-describedby` 关联到字段。

#### UI 参数（来自 UI_PROMPTS §M1）
| 类别 | 值 |
|---|---|
| 触发键 | 点 "+ New Library"（S2）/ 路由约定 |
| Modal 宽×高 | 600 × 640（PROMPTS 标 600；文档第 1 节标 520 — 冲突，以 PROMPTS 为准） |
| Radius | 20（radius-xl） |
| 背景 | bg bg-surface / shadow-lg |
| 蒙层 | rgba(15,15,20,.40) |
| Padding | 32（垂直 gap 20） |
| 关闭按钮 | "×" icon 顶右 |
| Title | h2 22/26.6 700 "Create a new Library" |
| Subtitle | body 14/22 text-secondary 2 行 |
| BaseInput Slug | 536×44，slugify 自动生成；helper body-sm text-tertiary "lowercase, digits, hyphens · 3–30 chars · permanent (can be renamed later, slug is fixed)" |
| BaseInput Display name | 536×44 |
| BaseTextarea Description | 536×72 |
| Primary language segmented | 3 个 pill 各 120×36 / radius 10 / 1px border-default / body-sm 600；选中：bg brand-50 / text brand-700 / 1px border brand-500 |
| Init help caption | text-tertiary 单行（描述初始化的存储） |
| Footer | Secondary "Cancel" 100×40 + Primary "Create Library →" 136×40 brand-500 |
| 错误 chip | warning-50 chip，文案 "Slug already exists" danger-700 |
| 键盘提示 | "↵ submit · Esc close" |

---

### M2 · DeleteConfirmModal（图 078）

**目的**：防止误删。

**视觉**：宽 480px；红色顶条；显式数据后果：
> Deleting library **graphrag-survey** will permanently remove:
> - **38 documents**
> - **14,218 chunks**
> - **2,431 entities** / **6,118 relations**
> - **47 chat sessions**

**字段**
- Confirmation input：用户必须**完整输入 slug**（如 `graphrag-survey`）才能解锁 Delete 按钮。
- Toggle "Hard delete (purge from object storage)" — 默认 off；开启时显示额外红色警告 + 30 天倒计时取消（mock，实际由后端实现 grace period）。

**交互**
- 输入实时比对 slug；按钮 disabled 直到完全匹配。
- Delete → POST `/v1/libraries/:id` `DELETE` → 关闭 modal → toast `Library deleted` 含 `Undo` 链（5s，仅 soft delete 可用）。
- 删除当前活动 library → 自动 `router.push('/libraries')` + libraryStore reset。
- **不**允许点击 overlay 或 Esc 关闭（用户必须显式取消 / 删除）—— 实际我们允许 Esc，但 Esc 显示二次提示 "Discard and close?"。

**A11y**
- 标题红色 `<h2>`，明示破坏性。
- `aria-describedby` 指向数据后果区块。
- Delete 按钮 disabled 时 `aria-disabled="true"` + tooltip "Type the slug to enable"。

#### UI 参数（来自 UI_PROMPTS §M2）
| 类别 | 值 |
|---|---|
| 触发键 | 库卡片菜单/Settings 中的 "Purge Library" |
| Modal 宽×高 | 600 × 560（文档第 1 节标 480 — 冲突，以 PROMPTS 为准） |
| Radius / bg / shadow | 20 / bg-surface / shadow-lg |
| Padding | 32 |
| Header icon | 48×48 圆 / bg danger-50 / glyph "⚠" 或 Lucide "alert-triangle" / danger-700 stroke 1.5 |
| Title | h2 22/26.6 700 'Purge "graphrag-survey"?'（slug mono 22 600 含引号） |
| Subtitle | body 14/22 text-secondary 2 行 |
| Impact card | 536×144 / radius 14 / bg danger-50 / 1px border-danger-500 @20% / padding 16 |
| Impact label | meta uppercase danger-700 "YOU WILL LOSE" |
| Impact list | body-sm danger-700 disc bullets（删库统计 chip：文档/chunk/实体/triples/索引/eval/session） |
| Confirm BaseInput | 536×44，校验 case-sensitive 完全匹配解锁 |
| Helper caption | text-tertiary "Match must be exact (case-sensitive). Delete button enables when the value matches." |
| Footer | Secondary "Cancel" 100×40 + Danger Primary "⊗ Purge Library" 136×40（bg danger-500 / text white） |
| Disabled 态 | text-disabled / bg bg-muted |

---

### M3 · CommandPaletteOverlay ⌘K（图 079）

**库选型**：推荐 `cmdk-vue`（社区移植），fallback 自实现壳 + `fuse.js`。
- `cmdk-vue` 优势：原生 Combobox 语义、prefix grouping、async items 一线流；劣势：维护活跃度一般，需关注。
- `fuse.js` 优势：模糊匹配成熟、稳定；劣势：要自己写交互层（上下键 / Enter / 分组）。
- **决策**：用 `cmdk-vue` 做框架 + `fuse.js` 做客户端模糊（entity / doc 列表 < 5k 项时）；entity > 5k 走后端 `/v1/search?q=`。

**视觉**：宽 720px，居中偏上（top: 18vh）；shadow + backdrop blur。

**结构**
```
┌─ Search input (autofocus) ─────────── Esc x ┐
│   [prefix indicator: ENTITIES | DOCS | …]   │
├──────────────────────────────────────────────┤
│ ENTITIES (3 of 246)                          │
│   ● Community detection — Method · 246 refs  │
│   ● Community summarization — Method · 152   │
│   ● Hierarchical communities (CD-C3)         │
│ DOCUMENTS                                    │
│   📄 Hierarchical Community Summary for KG QA│
│   📄 From Local to Global: A Graph RAG ...   │
│ ACTIONS                                      │
│   ⌘N  Generate review on "..."               │
│   ⌘L  Create a new library                   │
│   ⌘T  Open task page                         │
├──────────────────────────────────────────────┤
│ ↑↓ navigate  ⏎ open  / cycle  ⌘. settings    │
└──────────────────────────────────────────────┘
```

**Prefix 分组语法**
- `entity:graphrag` → 只搜实体
- `doc:rag survey` → 只搜文档
- `task:` → 当前进行的任务
- `cmd:` → 操作命令
- 不带 prefix → 全类聚合 + 加权排序

**交互**
- 打开：`⌘K` 全局（除非已在 input 内输入 `⌘K`，则透传）。
- 关闭：Esc / 点击 overlay / 选择 item 后。
- `/` 在 input 内循环切换 prefix。
- Enter：实体 → 跳 KG focus；文档 → 打开 M4 Drawer；动作 → 执行命令。
- `⌘` 修饰键：复制结果链接（不跳转）。
- 历史：localStorage 保存 last 10 entries，无 query 时显示。

**store**
```
commandPaletteStore.open() ← 全局快捷键 useCmdK()
  results = computed(() => {
    if (query) → fuse.search + 后端 fallback
    else → recent + suggested
  })
```

**A11y**
- `role="combobox" aria-expanded="true" aria-controls="cmdk-list"`。
- 列表 `role="listbox"`；选项 `role="option" aria-selected`。
- 屏读：每次列表变化 announce 数量。

#### UI 参数（来自 UI_PROMPTS §M3）
| 类别 | 值 |
|---|---|
| 触发键 | ⌘K / Ctrl+K（全局） |
| Modal 宽×高 | 720 × 560 |
| Radius / bg / shadow | 20 / bg-surface / shadow-lg |
| 蒙层 | rgba(15,15,20,.40) |
| Input 行 | 720×64 / padding 0 20 / 1px 底 border-subtle |
| Leading icon | Lucide "search" 18 text-tertiary |
| 输入字号 | body-lg 16/22 text-primary（+ blinking caret） |
| esc kbd chip | 28×20 / bg bg-subtle / mono-sm 600 |
| Body 区可滚动高 | 432 |
| Body padding | 16/12 横向 |
| Section 标签 | meta uppercase 11/13.3 text-tertiary（如 "ENTITIES IN graphrag-survey"） |
| 搜索结果行 | 704×36 / radius 8 |
| 激活行样式 | bg brand-50 / text brand-700 600 |
| Hover 行 | bg bg-subtle |
| 前缀 chip / 类型 dot | leading 12 KG 类型 dot；类型 chip 用 entity 颜色 token |
| Footer | 720×40 / bg bg-subtle / inset 1px top border-subtle / body-sm text-tertiary |
| 键盘提示 | "↑↓ navigate     ↵ open     tab cycle scope     ⌘↩ run     esc close" |
| 进入动效 | 200ms scale-from-0.96 |
| 关闭 | 点击 outside 关闭 |

---

### M4 · DocumentDetailDrawer（图 080）

**位置**：右抽屉，宽 720px（`<lg` 时全屏）。

**库选型**：PDF 预览
- 推荐 `vue-pdf-embed`（薄包，背后 pdfjs-dist）。
- 备选 `pdfjs-dist` 直接用（更大 bundle 但可控）。
- 决策：`vue-pdf-embed` 默认；当需要 annotation / highlight 时切 `pdfjs-dist`。

**Layout**
```
+----------------------+------------------+
| PDF Preview (canvas) | TOC outline      |
| 1fr                  | 240px            |
+----------------------+------------------+
| Chunk list (sticky bottom, expandable)  |
| - chunk#  page  preview text  (jump)    |
+----------------------------------------+
```

**交互**
- TOC click → PDF jump to page + 高亮该 section。
- Chunk row click → PDF 滚到该 chunk 起始位置 + 高亮 bbox（如果有）。
- "Open in chat" → `composerStore.prefill('Summarize chunk #88 from "<title>"')` → 跳 chat。
- 顶部 actions：Download / Re-ingest / Delete / Copy citation。
- 右上 close = Esc。

**store**
```
docDetailStore.load(docId) → meta + url
chunksStore.load(docId, page) → 分页加载
selectChunk(chunkId) → docDetailStore.scrollToBBox + 高亮 1.2s
```

**A11y**
- Drawer = `<aside role="dialog" aria-modal="true" aria-labelledby="dd-title">`。
- PDF canvas 是黑盒 — 同时提供 "Plain text view" tab 给屏读用户。
- TOC 用 `<nav>` + `<ol>` 真层级。

#### UI 参数（来自 UI_PROMPTS §M4）
| 类别 | 值 |
|---|---|
| 触发键 | 点 Documents 表行 / `/lib/:id/docs/:docId` |
| Drawer 宽×高 | 800 × 900（PROMPTS 800；文档第 1 节标 720 — 冲突，以 PROMPTS 为准） |
| Radius / bg / shadow | 右上 inset 20（可选）/ bg-surface / shadow-lg |
| 蒙层 | 30% 黑色覆盖于 Documents 页 |
| Padding | 32 / 垂直 gap 20 |
| Header title | h2 22/26.6 700（2 行截断） |
| Meta | body-sm text-secondary（1 行截断，作者 / 机构 / 年 / arXiv id） |
| StatusPill | 88×28 "● Ready" success |
| Stat row | 4 列各 80w（128 chunks · 94 entities · 218 triples · 22 pages）；数字 h2 22 700 / 标签 caption text-tertiary |
| 双栏 body gap | 24 |
| LEFT PDF preview 宽 | 336（"PDF preview" 占位 336×408） |
| LEFT SECTIONS 列 | "SECTIONS · 12" meta uppercase + 12 行 mono caption + body-sm |
| RIGHT 宽 | 336 |
| RIGHT chunks header | "CHUNKS · showing 3 of 128 · filter by section" meta uppercase |
| Chunk card | mono "chunk_2871" 前缀 + 位置 pill "§4.5 · p.4" + 2 行 italic body-sm text-secondary |
| 跳 chunk 高亮规则 | 选中 chunk → PDF 滚到 bbox + 高亮 1.2s（来自第 5 节 store） |
| Footer 区域 | 800×64 sticky bottom / inset 1px top border-subtle / padding 16 |
| Footer buttons | Secondary "↻ Re-parse" 152×40 / Primary "Open in Chat / Ask →" 200×40 brand-500 / Danger ghost "Remove document" 152×40 |

---

## 第三部分 · 边界态系统化设计

### A · Skeleton（图 081）

**原则**：Skeleton **必须与最终数据结构同构**，避免 loading→data 时布局跳动（CLS=0 目标）。

| 区域 | Skeleton 结构 |
|---|---|
| Dashboard KPI | 4× 矩形 120×80，gap 24 |
| Recent chats | 5× 行（头像圆 + 双行 line） |
| KG snapshot | 圆形 mosaic SVG 占位 |
| Chat conversation | alternating user/assistant 气泡 placeholder（3 条） |
| EvidencePanel | 3× 卡片骨架 |

**动画**
- 默认 shimmer（CSS linear gradient + animation 1.4s）。
- `@media (prefers-reduced-motion: reduce)` → 仅纯灰底，禁动画。
- 超时（>3s）：底部 inline note "Still loading... [Retry]"。

#### UI 参数（来自 UI_PROMPTS §06-A）
| 类别 | 值 |
|---|---|
| 触发 | 首次加载 / 路由切换 |
| 骨架尺寸 | LibraryCard 320×220 / KPICard 336×128 / Document row / ChatMessage |
| Shimmer 时长 | 1.2s（PROMPTS 标 1.2s；文档第 1 节标 1.4s — 冲突，以 PROMPTS 为准） |
| Shimmer 颜色 | bg-muted #EAEAE5 → bg-subtle #F4F4F1（gradient pulse） |
| 布局 | 2×2 grid + 文字 caption 命名各项 |
| 严重度色 | neutral |
| 是否可恢复 | 是（数据到达后替换） |

---

### B · Stream-break 错误（图 082）

**触发**：SSE 在 `done` 之前断开（network drop / server 5xx / 用户跨网络切换）。

**UI**
- 已输出 token **完整保留**（不擦除）。
- 在 assistant 气泡尾部追加 inline chip：
  ```
  ⚠ Stream interrupted (network)
     [Retry]  [Continue from here]  [Stop]
  ```
- `Retry`：从原 prompt 重发整条。
- `Continue from here`：发新请求 `prompt = original + already-generated`，server 续写。
- `Stop`：标记 partial-error，结束。

**store**
```
useSSEChat.onError(err) →
  chatStore.markPartialError(msgId, err)
  if (err.retryable) showRetryChip(msgId)
notification: 不弹 toast（已有 inline），仅写 errorLog
```

#### UI 参数（来自 UI_PROMPTS §06-B）
| 类别 | 值 |
|---|---|
| 触发 | SSE 在 done 前断连 |
| Inline chip 行 | 单行 / body-sm / danger-700 / weight 600 |
| 主文案 | "Stream interrupted. Retry" |
| Retry 链接 | underlined / body-sm 600 / brand-600 |
| Tooltip | "Connection lost at token 1,247 — context preserved." |
| 位置 | 紧贴 assistant 消息最后部分段落下方 |
| 严重度色 | danger（danger-700 文字 / 无背景） |
| 是否可恢复 | 是（点 Retry 续接） |

---

### C · 0-hit Evidence Empty（图 083）

**触发**：retrieval 返回 0 chunk。

**禁忌**：不写"No results."。

**正确做法 — 给 3 个出路**
```
We couldn't find evidence for this question in *graphrag-survey*.
Try:
  1. Broaden the query (suggest 3 reformulations using LLM rewrite)
  2. Switch reranker → BGE base / mxbai (current: cohere)
  3. Search across all libraries → opens M3 CommandPalette with prefix
```
- 三条都给可点击 CTA。
- 同时显示 "Submit feedback: this question should have results" 收集 silent failure。

#### UI 参数（来自 UI_PROMPTS §06-C）
| 类别 | 值 |
|---|---|
| 触发 | retrieval 返回 0 chunk |
| Illustration | 40×40 圆 / bg bg-subtle #F4F4F1 / Lucide "search-x" 20 / text-tertiary |
| Title | h4 600 "No evidence found" |
| Body | body-sm text-secondary（max-w 320，最多 2 行）"Try widening the year filter, lowering confidence to 0.5, or uploading more papers to this Library." |
| Primary outline button | "Adjust filters" body-sm 600 brand-600 |
| 3 个建议 chip 样式 | （PROMPTS 用 3 条建议文字嵌入正文，未单独画 chip）— 建议性文本嵌入 body |
| 位置 | EvidencePanel 内居中 |
| 严重度色 | neutral（非告警） |
| 是否可恢复 | 是（调整过滤后重试） |

---

### D · Budget Exceeded Banner（图 084）

**两层提示**
1. **Page-level Banner**（sticky top under TopBar）
   ```
   ⛔ Budget exceeded · You've used $9.87 / $10.00 this month.
   [Upgrade]  [View usage]
   ```
2. **拦截 expensive 动作**：
   - Composer "Send" 按钮变 disabled + tooltip "Budget exceeded · Upgrade to send"。
   - Review "Generate" 同理 disabled。
   - KG build / re-ingest 同理。
   - 但 **read-only 操作仍可用**（看历史 chat / 看 KG / 看文档）。

**store**
```
costStore.budget$  // observable
budgetGuard(action) {
  if (action.cost && costStore.exceeded) → block + showBanner
}
```

#### UI 参数（来自 UI_PROMPTS §06-D）
| 类别 | 值 |
|---|---|
| 触发 | 预算超额（成本 vs 限额） |
| Banner 尺寸 | 712×32（inline，Composer 上方） |
| Radius | 10 |
| Background | bg danger-50 #FDF1F1 |
| Border | 1px border-danger-500 @30% |
| Padding | 8 / 12 |
| 图标 | "⚠" danger-700 16 |
| 主文案 | body-sm 600 danger-700 "Budget exceeded." + body-sm danger-700 "Increase or simplify the question." |
| Trailing link | "Adjust budget" body-sm 600 brand-600 |
| 严重度色 | **danger**（danger-500 #EE4444 边 + danger-50 bg + danger-700 #B91B1B 文） |
| 是否可恢复 | 是（调整预算/简化问题后恢复） |

---

### E · Worker Offline Banner（图 085）

**触发**：心跳丢失（`/health` 30s 无响应）。

**UI**
- 全局 Banner（顶端，橙色）："Workers offline — running in read-only mode · Reconnecting..."
- 自动重连：exponential backoff（2s/4s/8s/16s/30s/30s...）。
- 重连成功 → Banner 变绿 "Back online" 2s 后消失。

**离线只读**
- 缓存的 chat history（IndexedDB）可读。
- KG 缓存可读（最后一次成功加载的 snapshot）。
- 文档列表可读，但不能上传 / 删除。
- 所有 mutation 按钮 disabled。
- Composer：保存草稿到 localStorage，提示 "Draft saved — will send when online"。

#### UI 参数（来自 UI_PROMPTS §06-E）
| 类别 | 值 |
|---|---|
| 触发 | `/health` 30s 无响应 |
| Topbar 微态 | NotificationBell 加 8 danger-500 dot |
| Offline pill 高 | 22h（pill 形） |
| pill 配色 | bg danger-50 + 文 body-sm danger-700 "⊘ Worker offline" |
| Tooltip | "Ingest worker offline. Uploads queued." |
| Auto-retry 倒计时字号 | —（PROMPTS 未规定字号；文档第 1 节定义 exp-backoff 2s/4s/8s/16s/30s） |
| 全局 Banner 样式 | （PROMPTS 在 06-E 只画 topbar 微态；page-level 全局 banner 由文档第 1 节定义为顶端橙色文字） |
| 严重度色 | danger |
| 是否可恢复 | 是（自动 reconnect，成功后变 success "Back online" 2s 消失） |

---

### F · Toast 系统（图 086）

**Layer 优先级**
| 级别 | 颜色 | 自动消失 | 适用 |
|---|---|---|---|
| info | 蓝 | 4s | "Library switched to..." |
| success | 绿 | 4s | "Document uploaded" |
| warning | 橙 | 6s | "Approaching budget limit" |
| error | 红 | 不自动 | API 异常（必须用户 ack） |
| progress | 灰 + 进度条 | 任务完成时变 success | "Generating review..." |

**规则**
- 同一来源 toast 自动合并（同 key 替换内容）。
- 最多同屏 3 个，超出排队。
- 位置：右下角，桌面；顶部，移动。
- 永远不阻塞输入（不挡 Composer）。

#### UI 参数（来自 UI_PROMPTS §06-F）
| 类别 | 值 |
|---|---|
| 触发 | 任务事件 / API 反馈 |
| 位置 | top-right（PROMPTS）；文档第 1 节为右下 / 移动顶部 — 冲突，以 PROMPTS 位置为准 |
| 边距 | 24（距离视口边） |
| 垂直 gap | 12 |
| Toast 单条尺寸 | 360×72（标准），单行时 360×64 |
| 左边 accent bar | 4px / 颜色随严重度 |
| 状态 icon | 20 |
| Title | body-sm 600 |
| Sub | body-sm text-secondary |
| 关闭 | "×" 图标 |
| 4 severity 颜色 | success #10B881 / info #06B6D3 / warning #F59E0A / danger #EE4444 |
| 自动消失时长 | 默认 4s（PROMPTS 未明示，沿用 03 组件规范 4s） |
| 严重度 token 对照 | success-500 / info-500 / warning-500 / danger-500 |
| 是否可恢复 | 是（含 action 链接如 Retry / Open task ↗ / Rebuild now） |

---

### G · Cross-Library Misroute（图 087）

**触发**：URL `:libraryId` 不存在 / 用户被踢出该 library / sessionId 属于另一 library。

**处理**
1. 路由守卫 `libraryGuard`：navigate beforeResolve → 调 `/v1/libraries/:id` HEAD → 404 / 403。
2. **不要 redirect 到 /libraries 直接吞掉错误**。展示明确页：
   ```
   Library "foo-bar-baz" was not found in your account.

   Did you mean one of these recently visited libraries?
   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
   │ graphrag-survey    │  │ medical-rag        │  │ personal-notes     │
   │ 38 docs · 2h ago   │  │ 124 docs · 1d ago  │  │ 12 docs · 3d ago   │
   └────────────────────┘  └────────────────────┘  └────────────────────┘

   Or [Create a new library]
   ```
3. 顶部 sticky AlertBanner 同时显示，便于复现："Library 'foo-bar-baz' was not found. Redirected to /libraries."
4. 错误进 errorLog（telemetry）。

#### UI 参数（来自 UI_PROMPTS §06-G）
| 类别 | 值 |
|---|---|
| 触发 | URL `:libraryId` 不存在 / 无权限 |
| 落地页 | LibraryDashboard 顶部 toast slot |
| Toast 文案 | "⊘ Library 'foo' does not exist. Redirected to /libraries." |
| Auto-dismiss | 6s |
| Action 链接 | "Create 'foo' →" brand-600 link |
| 404 illustration 尺寸 | —（PROMPTS 06-G 只画 toast；推荐 library 卡片来自 LibraryCard 03-AJ） |
| 推荐 library 卡片样式 | 来自 LibraryCard（与 S2 4-列 grid 一致：220h / radius 14 / 1px border-subtle） |
| 严重度色 | warning（toast 黄/danger 红） |
| 是否可恢复 | 是（点 "Create →" 或选历史 library） |

---

## 第四部分 · 3 条关键旅程的时序编排（核心）

### J1 · 首次使用 → 第一答案（图 088）

```
┌─[Step 1] /onboarding ─────────────────────────────────────────┐
│ 显示 3 介绍卡 + CTA "Create your first library"               │
│ a11y 焦点: CTA 按钮                                            │
│ 触发: click / Enter                                             │
│ 调用: openModal('library-create')                              │
│ 动画: modal slide-up 200ms ease-out                            │
│ 失败回退: 无（纯前端）                                          │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 2] M1 LibraryCreateModal ───────────────────────────────┐
│ 用户填 Name=GraphRAG Survey, slug 自动生成 "graphrag-survey"   │
│ a11y 焦点: Name 输入框                                          │
│ 调用: HEAD /v1/libraries/graphrag-survey (uniqueness)          │
│ 调用: POST /v1/libraries → {id:"lib_88", slug:"..."}           │
│ 动画: 提交按钮 spinner; 成功后 modal fade-out 150ms             │
│ store: libraryStore.create(...) → setActive(lib_88)            │
│        onboardingStore.markCompleted()                          │
│ 失败回退: inline error 在错误字段; 不关闭 modal                 │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 3] toast + router.push(/lib/lib_88/docs?onboarding=1) ──┐
│ toast: "Library created" · 4s · success                         │
│ a11y 焦点: 主 DropZone (autofocus)                             │
│ 视觉: DropZone 高亮 pulse (橙色 boxshadow, 3s)                 │
│ 提示文字: "Drop your first PDFs here"                          │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 4] 用户拖入 3 个 PDF ────────────────────────────────────┐
│ 触发: drop event                                                │
│ 调用: POST /v1/libraries/lib_88/documents (multipart)          │
│ store: docsStore.startUpload([file1, file2, file3])            │
│ UI: 表格出现 3 行, 状态 "uploading" → "parsing" → "chunking"   │
│     → "embedding" → "indexed"  (SSE 推进度)                    │
│ a11y: aria-live 通报 "1 of 3 documents ready"                  │
│ 失败回退: 该行变红 + Retry icon; 其他行继续                     │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 5] 第一个 doc indexed → 顶部 CTA pulse ─────────────────┐
│ 触发: docsStore.firstReady event                                │
│ UI: 顶部出现 sticky banner: "Ready to try a question? [Open Chat]" │
│ 同时 SideNav 上 "Chat" 项目轻微 pulse                          │
│ 触发可手动跳; 也可等所有 docs 完成                              │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 6] router.push(/lib/lib_88/chat?onboarding=1) ──────────┐
│ 视觉: 空 session, EmptyState 居中                              │
│       三个 sample question chips:                              │
│         "What's this corpus about?"                            │
│         "List the main methods discussed."                     │
│         "Compare paper A vs paper B on metric X."              │
│ a11y 焦点: Composer (但显示 sample chips 在上方)                │
│ 用户点 chip → composerStore.draft = chip.text → 自动 submit    │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 7] SSE stream begins → 第一个答案 ──────────────────────┐
│ event: token 流入, 气泡逐字显现                                │
│ event: citation 流入, EvidencePanel 自动展开 (即使之前折叠)    │
│        每张卡片淡入 200ms                                       │
│ event: done → CitationChip 数组定型, 反馈按钮出现              │
│ a11y: aria-live polite, 节流 250ms                             │
│ 失败回退: stream 中断 → 状态 B (保留已输出 + retry)             │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌─[Step 8] Onboarding 关闭, query 清除 ─────────────────────────┐
│ router.replace 去掉 ?onboarding=1                              │
│ onboardingStore.dismissed = true                                │
│ 此后再访问 /onboarding 显式才会显示                             │
└────────────────────────────────────────────────────────────────┘
```

**总用时目标**：从 Step 1 到 Step 7（第一答案首 token）≤ 90 秒（含 3 PDFs ingest）。

#### UI 参数（来自 UI_PROMPTS §J1）
| 类别 | 值 |
|---|---|
| Storyboard 画板尺寸 | 2880×900 |
| 缩略图数量 / 单图 | 6 / 440×900 |
| 缩略图间 gap | 48 |
| 连接线 | 细线 brand-200 #B2BCF4 水平箭头 + 转场 chevron |
| 标题位置 | 整板中央上方 h2 "J1 · First use → first answer" |
| 步骤 caption（上） | meta uppercase text-tertiary "Step n · …" |
| 步骤描述（下） | body-sm text-secondary 单行 |
| 关键 hero | Step 1 = Onboarding S1 mini；Step 5 = Chat S3 流式首答 + EvidencePanel 3 卡 |
| 关键 CTA | Step 1 "Create your first Library" / Step 6 click `[1]` chip → 自动滚到证据卡 |
| Transition 时长 | modal slide-up 200ms / fade-out 150ms / pulse 3s / aria-live 250ms 节流 / CitationChip 高亮 600ms |

---

### J2 · 综述长任务（图 089）

```
[Step 1] /lib/:id/chat   →   用户在 chat 中触发 /slash 命令 "/review topic=..."
                              或 SideNav 点 "Review" → 跳 S5b
                              ↓
[Step 2] /lib/:id/review (S5b configure)
   - 表单: topic / sections template / depth / reranker / budget
   - 右上 sticky cost preview (debounce 500ms)
   - "Generate" 按钮 disabled until topic 非空 + budget OK
                              ↓
[Step 3] POST /v1/tasks {type:review, config} → 返回 taskId
   - router.push(/lib/:id/review/:taskId)
   - useTaskStream(taskId) 立即建 SSE 连接
                              ↓
[Step 4] S5 in-progress 视图
   - PipelineTree 实时点亮 step
   - DraftStream 逐 token 流入
   - LiveCitationList 同步追加
   - RunStats footer band 实时更新 (elapsed, tokens, cost)
   - a11y: aria-live 仅广播 section 变更 ("Generating section 3 of 7")
                              ↓
[Step 5] "Run in background" 按钮
   - taskStore.minimize(taskId)
   - 主区返回 S5b configure 态 (或用户自由导航)
   - 全局右下角浮现 mini-progress pill:
       ┌──────────────────────┐
       │ ◐ Review · 47% · 12m  │
       └──────────────────────┘
   - SSE 仍在跑, store 持续更新
                              ↓
[Step 6] 用户在 /lib/:id/chat 继续问题, 任务并行进行
   - 全局任务条不会被遮挡
   - 多个 task 时 pill 堆叠 (最多 3, 超出折叠为 "+ 2")
                              ↓
[Step 7a] 失败路径
   - event: error code=WORKER_OOM → taskStore.markFailed
   - notification: toast error "Review failed at section 4 · Resume / Retry / Cancel"
   - 用户点 "Resume from section 4" → POST /v1/tasks/:id/resume
   - 已生成 sections 保留在 reviewStore
                              ↓
[Step 7b] 成功路径
   - event: done → notificationStore.push('Review ready', taskId)
   - 红点出现在 NotificationBell
   - mini pill 变绿 "✓ Review ready"
   - 用户点 pill → router.push(/lib/:id/review/:taskId)
                              ↓
[Step 8] S5 完成态
   - DraftStream 变 ReadView (markdown rendered)
   - 顶部 action bar: Export markdown / Export PDF / Regenerate section / Share
   - "Discuss in chat" 按钮 → composerStore.prefill 跳 chat
```

**核心机制**
- **后台运行 = SSE 不掉，UI 折叠**。store 是 single source of truth；UI 只是它的 projection。
- **断点续 = 任务级 checkpoint**。每个 section 完成后 server 持久化，client 也持久化 reviewStore（IndexedDB）。
- **可取消 = 立刻响应**。POST `/v1/tasks/:id/cancel` 立即 200，server 异步停 worker；UI 立刻进 "Cancelling..." 状态。

#### UI 参数（来自 UI_PROMPTS §J2）
| 类别 | 值 |
|---|---|
| Storyboard 画板尺寸 | 2880×900 |
| 缩略图数量 / 单图 | 5 / 440×900（与 J1 一致比例） |
| 连接线 | brand-200 chevron |
| 标题 | "J2 · Review long-task with background hand-off" |
| 关键 hero | Step 3 = Review IN-PROGRESS S5 中流；Step 5 = 完成 toast "✓ Review complete — Open ↗" |
| 关键 CTA | "Run in bg ↗" → topbar NotificationBell 出红点 |
| Transition 时长 | mini-progress pill 折叠 200ms / toast 4s 自动消失 / red dot 立即 |

---

### J3 · KG 探索 → 反馈到 Chat（图 090）

```
[Step 1] /lib/:id/kg  (S4)
   - 用户看 entity A = "GraphRAG"
   - 节点 click → EntityDetailDrawer 弹出
                              ↓
[Step 2] 右键 entity A → 上下文菜单 "Find paths to..."
   - 弹出 entity picker (内嵌 mini-cmdk)
   - 用户选 entity B = "Community Summarization"
                              ↓
[Step 3] router.push(/lib/:id/reason?from=e_A&to=e_B&maxHop=3)
   - S7 视图加载
   - SSE path-found 实时追加路径
   - 路径按 confidence 排序, 默认展开 top-3
                              ↓
[Step 4] 用户点 path #2 中某 chunk
   - EvidenceCard popover 弹出, 显示原文片段 + 来源 doc
   - popover 上有 "Discuss in chat" 按钮
                              ↓
[Step 5] 点 "Discuss in chat"
   - composerStore.prefill(
       "Based on the path [GraphRAG]—uses→[Hierarchical clustering]—produces→[Community Summarization]:\n\n"
     )
   - evidenceStore.pinForNextMessage([chunk_id_1, chunk_id_2, chunk_id_3])
       // 这些 chunks 会作为 hint 注入 retrieval, 提升相关性
   - router.push(/lib/:id/chat?prefill=1)
                              ↓
[Step 6] /lib/:id/chat
   - Composer 已预填提示 + 光标置于末尾
   - EvidencePanel 已显示 pinned chunks (顶部置顶, 标签 "From KG path")
   - 用户补完问题 → 发送 → SSE
                              ↓
[Step 7] Chat 答案返回, 含 CitationChip
   - CitationChip click → 反向高亮 KG 节点
       → router.push(/lib/:id/kg?focus=chunk_chain) + 高亮 600ms
   - 形成 KG ↔ Chat 双向闭环
```

**核心机制**
- **prefill 是 composerStore 的临时状态**，发送或离开 chat 时清除（不污染下一个 session）。
- **pinned evidence 是 evidenceStore 的 hint**，仅影响下一条 message 的 retrieval，不长期占用上下文（避免 cost 漂移）。
- **双向跳转**用 `from` query 记录来源：`?from=kg&entity=e_A`，方便埋点 + UX "Back to KG" 按钮。

#### UI 参数（来自 UI_PROMPTS §J3）
| 类别 | 值 |
|---|---|
| Storyboard 画板尺寸 | 2400×900 |
| 缩略图数量 / 单图 | 4 / 600×900（PROMPTS 未明确，按 2400/4 推算 600；实际可与 J1/J2 440 对齐） |
| 连接线 | brand-200 chevron |
| 标题 | "J3 · From KG to Chat" |
| 关键 hero | Step 1 = KG canvas 默认；Step 4 = Chat S3 prefill composer |
| 关键 CTA | "Ask about GraphRAG in Chat →" → prefill composer "Tell me about GraphRAG" + active library pill |
| Transition 时长 | KG node settle 320ms / CitationChip 反向高亮 600ms |

---

## 第五部分 · 全局架构清单

### Pinia Store 划分

| Store | 职责 | 跨库重置 | 持久化 |
|---|---|---|---|
| `authStore` | 用户、token、me | ✗ | localStorage（refresh token） |
| `libraryStore` | 当前 library / 列表 | n/a | URL + localStorage（recent） |
| `chatStore` | 会话与消息 | **✓** 切库清空 | IndexedDB（缓存当前 lib） |
| `composerStore` | 草稿、prefill、pinned chunks | **✓** | localStorage（草稿） |
| `evidenceStore` | 证据卡片、by-message 映射 | **✓** | session memory |
| `kgStore` | 图、focus、filters | **✓** | session memory |
| `reasonStore` | 路径推理结果 | **✓** | session memory |
| `hypothesisStore` | 假设卡 + thumbs | **✓** | server-side |
| `docsStore` | 文档列表、ingest 进度 | **✓** | session memory |
| `taskStore` | 长任务、minimized list | **✓** | IndexedDB |
| `reviewStore` | 综述草稿、章节状态 | **✓** | IndexedDB（断点续） |
| `reasoningTraceStore` | 深度模式 trace 树 | **✓** | session memory |
| `costStore` | 用量与预算 | ✗ | localStorage（缓存） |
| `notificationStore` | bell 列表 | ✗ | server-side |
| `settingsStore` | router / embedder / schema | 部分（lib-level） | server-side |
| `commandPaletteStore` | open state + recent | ✗ | localStorage（recent） |
| `onboardingStore` | dismissed / step | ✗ | localStorage |
| `chatLayoutStore` | 三栏折叠态 | ✗ | localStorage |

**切库重置规则**（关键）：
```ts
router.beforeEach((to, from) => {
  if (to.params.id !== from.params.id) {
    chatStore.$reset();
    composerStore.$reset();
    evidenceStore.$reset();
    kgStore.$reset();
    reasonStore.$reset();
    hypothesisStore.$reset();
    docsStore.$reset();
    taskStore.scopeTo(to.params.id);
    reviewStore.scopeTo(to.params.id);
  }
});
```

### 全局 Composables

| Composable | 职责 |
|---|---|
| `useSSEChat` | Chat 的 SSE 连接、token / citation / trace 事件路由 |
| `useTaskStream` | 长任务（review/reason/hypothesize）SSE 复用 |
| `useCmdK` | 全局 ⌘K 监听 + commandPaletteStore 联动 |
| `useShortcuts(map, scope?)` | scope 化键盘绑定（自动 cleanup） |
| `useToast` | 推送 toast，支持 `useToast.error / success / progress` |
| `useAsyncResource(fetcher)` | 通用 `loading / data / error / refetch` 状态机 |
| `useTokenStream` | 通用 SSE token 节流到 rAF 批渲染 |
| `useFocusReturn` | 关闭 modal 后焦点归位 |
| `useUnsavedGuard(isDirty)` | 离开页二次确认 |
| `useIngestProgress(libId)` | 文档上传进度 SSE 单连接 |

### 路由守卫

```ts
const router = createRouter({...})
router.beforeEach(authGuard)         // 未登录 → /login
router.beforeEach(libraryGuard)      // libraryId 不存在 → G 误路由页
router.beforeEach(unsavedGuard)      // 任务运行 / 草稿未发 → confirm
router.beforeResolve(prefetchGuard)  // 预取该路由必需数据 (library meta)
router.onError(routeErrorHandler)    // 路由级错误 → ErrorBoundary
```

### 错误边界

- 路由级 `<RouteErrorBoundary>` 包整个 `<router-view>`。
- 局部 `<ErrorBoundary>` 包高风险组件（KG canvas、PDF preview、Markdown 渲染）。
- 全局 `window.addEventListener('unhandledrejection', ...)` → errorLog + 静默 toast。

### 全局快捷键 Map

| 键 | scope | 行为 |
|---|---|---|
| `⌘K / Ctrl+K` | global | CommandPalette |
| `⌘/` | global | 焦点跳到 SideNav search |
| `⌘B` | global | 折叠 SideNav |
| `⌘.` | chat | 切深度模式 |
| `⌘[` `⌘]` | chat / kg | 折叠左 / 右栏 |
| `⌘Enter` | composer | 发送 |
| `Shift+Enter` | composer | 换行 |
| `Esc` | global | 关闭 modal / popover / 停止 SSE |
| `J / K` | chat list | 上下定位消息 |
| `G then L` | global | 跳 `/libraries` |
| `G then C` | global | 跳当前 library 的 `/chat` |
| `G then K` | global | 跳当前 library 的 `/kg` |
| `?` | global | 显示快捷键 cheatsheet modal |
| `⌘S` | settings forms | 保存 |

---

## 第六部分 · 3 条产品级铁律（最值得固化）

### 铁律 1 · 任何 LLM 输出必须可追溯到具体 chunk

**含义**
- assistant 消息若没有 ≥1 citation chip，**不渲染气泡正文**；显示警告："Cannot answer without evidence."
- review draft 同理：每段至少 1 citation，否则段落标红 + "Unsubstantiated"。
- hypothesis 卡片：必须列 ≥2 支撑 chunks 才能显示 thumbs。

**强制点**
- SSE `done` 事件到来时，若 citation count = 0 → chatStore 改为 `unsubstantiated` 状态。
- 不留任何"看起来合理但没引用"的输出，杜绝幻觉伪装。

### 铁律 2 · 切库 = 重置上下文，绝不跨库混淆

**含义**
- LibrarySwitcher → router.push → store reset（见上）。
- chatStore / evidenceStore / kgStore 等 library 级 store 必须 `scopeTo(libraryId)`。
- 任何后端 API 调用 URL 必须带 `:libraryId`；client 拦截器校验 `libraryId === route.params.id`，不匹配直接抛错。
- commandPalette 默认仅搜当前库；跨库搜索是显式 opt-in（输入 `lib:*` prefix）。

**强制点**
- E2E 测试：切库后断言 store 全空 + URL 已改。
- 静态分析：禁止任何代码引用 `chatStore.libraryId !== currentLibraryId` 的旧消息。

### 铁律 3 · 长任务必须可后台、可断点续、可取消

**含义**
- 任何运行时长 >30s 的任务：
  - 必须支持 "Run in background"（minimize 到 mini pill）。
  - 必须 server-side checkpoint（每 section / 每路径节点）。
  - 必须 `POST /v1/tasks/:id/cancel` 立即响应。
  - 失败必须可 `resume` 从最后 checkpoint。
- 全局右下角 floating task bar 永远可见运行中任务；多任务自动堆叠。

**强制点**
- taskStore.create 必须返回 `{taskId, supportsBackground, supportsResume, supportsCancel}`；缺一项 = 不合规任务，UI 拒绝启动。
- E2E：任务运行中刷新页面 → 刷新后 mini pill 自动恢复 + SSE 重连。

---

## 附录 A · 性能预算

| 指标 | 目标 |
|---|---|
| First Contentful Paint | < 1.2s |
| Largest Contentful Paint | < 2.5s |
| Cumulative Layout Shift | < 0.05 |
| First chat token TTFB | < 800ms |
| SSE token render rate | 节流到 60fps |
| 路由切换 | < 200ms (前置 prefetch) |
| Modal 打开 | < 100ms |
| KG canvas 渲染 (≤2k 节点) | < 500ms 初始 |

## 附录 B · A11y 检查清单

- [ ] 所有 modal `role="dialog" aria-modal="true"` + focus trap
- [ ] 流式消息 `aria-live="polite"` 节流广播
- [ ] KG canvas 提供 list view 等价物
- [ ] PDF preview 提供 plain text view
- [ ] 所有快捷键有 cheatsheet（`?` 弹出）
- [ ] 颜色对比度 WCAG AA（正文 4.5:1，大文本 3:1）
- [ ] 全键盘可达（Tab 顺序合理，不卡焦点）
- [ ] `prefers-reduced-motion` 关闭所有非必要动画
- [ ] 错误信息有文本，不仅依赖颜色

## 附录 C · 库选型决策表

| 用途 | 选型 | 理由 | 备选 |
|---|---|---|---|
| CommandPalette 框架 | `cmdk-vue` | 语义化 combobox, prefix 分组原生支持 | 自实现 + `fuse.js` |
| 模糊搜索 | `fuse.js` | 稳定、轻、零依赖 | `flexsearch` |
| KG 渲染 (<5k 节点) | `cytoscape.js` | API 友好、丰富布局 | `g6` |
| KG 渲染 (>5k 节点) | `sigma.js` | WebGL 性能极佳 | `cosmos` |
| PDF preview | `vue-pdf-embed` | 薄包好集成 | `pdfjs-dist` 直用 |
| Markdown 渲染 | `markdown-it` + `shiki` (lazy) | 可控、流式增量友好 | `marked` |
| 虚拟列表 | `vue-virtual-scroller` | 文档表、长会话 | `@tanstack/vue-virtual` |
| 表单 | `vee-validate` + `zod` | schema 校验复用 | `formkit` |
| SSE | `fetch` + ReadableStream 手写 | 支持 Authorization header | `@microsoft/fetch-event-source` |
| Toast | `vue-sonner` | 轻、好看、可堆叠 | 自实现 |
| Focus trap | `focus-trap` | 成熟、嵌套支持 | 自实现 |

---

_文档版本 v1.0 · 与 01–07 文档配套使用 · 任何修改需同步更新对应屏幕组件库引用。_

---

## 附录 D · 速查表（来自 UI_PROMPTS 汇总）

### D.1 · 8 屏 Layout 速查表

| 屏 | Grid 列宽 | 容器 max-w | 主区 padding | 关键 region 高 | 断点 <lg 行为 |
|---|---|---|---|---|---|
| S1 Onboarding | 单列 max-w 720（无 SideNav） | 1440 | hero 垂直节奏 24 | hero —；Step Card 200 | — |
| S2 Library Dashboard | 4 列 / gap 20（无 SideNav） | 1440 | 32 | grid 一行 220；底部 sticky 40 | — |
| S3 Chat ★ | 240 / 760 / 440（SideNav / Conv / Evidence） | 1440 | Conv 32 | Composer 112 min；EvidencePanel 折叠宽 44 | 折成 Tabs（Conv / Evidence / Sessions） |
| S4 KG Browser | 240 / 280 / 560 / 360（Nav / Filter / Canvas / Detail） | 1440 | — | Canvas footer legend 24 | FilterPanel 顶部 Sheet |
| S5 Review In-Progress | 320 / 688 / 336（Tree / Draft / Cite） | 1440 | 24 | 每列 784 | — |
| S5b Review Config | 单列卡 720×620 居中 | 1440 | 卡 padding 40 | Topic Textarea 96；Run 按钮 44 | — |
| S6 Documents | 单列（DropZone 1376 + 表格 1376） | 1440 | 32（gap 24） | DropZone 120；表格 524；sticky 40 | — |
| S7 Reason / Hypo | prose 720 / path 1024 | 1440 | 32 | Question 88；Path 320；Timeline 252；HypothesisCard 180/88 | — |
| S8 Eval + Settings | 64/36（Chart 864 / Settings 496） | 1440 | 32（gap 24） | Chart 280；Settings 552；FailureCaseTable 248 | — |

### D.2 · 4 Modal 尺寸速查表

| Modal | 宽 × 高 | Radius | Padding | 蒙层 | 触发键 / 入口 |
|---|---|---|---|---|---|
| M1 LibraryCreateModal | 600 × 640 | 20 | 32（垂直 gap 20） | rgba(15,15,20,.40) | S2 "+ New Library" |
| M2 DeleteConfirmModal | 600 × 560 | 20 | 32 | rgba(15,15,20,.40) | Library 菜单 "Purge" / Settings DATA "Purge Library" |
| M3 CommandPaletteOverlay | 720 × 560（input 64h；body 滚动 432） | 20 | input 0/20；body 16/12 | rgba(15,15,20,.40) | ⌘K / Ctrl+K |
| M4 DocumentDetailDrawer | 800 × 900（右抽屉） | 右上 20（可选） | 32（垂直 gap 20）；footer 16 | 30% 黑 | S6 表行点击 / `/lib/:id/docs/:docId` |

### D.3 · 7 边界态触发与样式速查表

| 态 | 触发条件 | 表现 | 严重度色 | 是否可恢复 |
|---|---|---|---|---|
| A Skeleton | 首次加载 / 路由切换 | 4 卡 2×2 grid（LibraryCard 320×220 / KPICard 336×128 / Doc row / ChatMessage）；shimmer 1.2s；bg-muted → bg-subtle | neutral | 是（数据到达替换） |
| B Stream-break | SSE done 前断连 | 末段下方 inline；body-sm 600 danger-700 "Stream interrupted. Retry"（Retry = brand-600 下划线） | danger | 是（Retry / Continue） |
| C 0-hit Evidence | retrieval 返回 0 chunk | 40×40 圆 search-x；h4 "No evidence found" + body-sm 提示 + "Adjust filters" outline | neutral | 是（放宽过滤后重试） |
| D Budget Exceeded | 成本超额 | 712×32 inline banner；radius 10；bg danger-50；1px danger-500 @30%；"Budget exceeded." + "Adjust budget" link | **danger** | 是（调预算/简化问题） |
| E Worker Offline | `/health` 30s 无响应 | Topbar pill 22h "⊘ Worker offline" bg danger-50 / 文 danger-700；Bell 加 8 danger-500 dot；全局 banner（橙）+ exp-backoff 2/4/8/16/30s | danger | 是（自动 reconnect） |
| F Toast 系列 | 任务 / API 事件 | top-right 24 边距 / 12 gap；360×72 或 ×64；4px 左 accent；icon 20；默认 4s 自动消失 | success / info / warning / **danger** | 含 action（Retry / Open / Rebuild） |
| G Cross-Library Misroute | URL :id 不存在 / 无权限 | LibraryDashboard 顶 toast 6s 自动消失；文案 "⊘ Library 'foo' does not exist. Redirected to /libraries."；action "Create 'foo' →" brand-600 | warning（toast） | 是（创建 / 选历史 lib） |

> 颜色 token 全部双写：danger-500 #EE4444 / danger-50 #FDF1F1 / danger-700 #B91B1B；success-500 #10B881；info-500 #06B6D3；warning-500 #F59E0A；brand-500 #4F46E4 / brand-200 #B2BCF4 / brand-50 #EDF0FF。


