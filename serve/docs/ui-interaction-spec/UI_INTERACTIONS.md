# UI 交互规范总入口 — RAG-KG Copilot

> `UI_GALLERY.md` 提供视觉（90 张图），本文档配套提供**交互**。每节图集对应一份子文档，含组件状态机、键盘可达、A11y、动效、Vue 实现细节与跨组件联动。技术栈见 `FRONTEND_TECH_STACK.md`。

---

## 子文档索引

| # | 主题 | 覆盖图集 | 路径 | 行数 |
|---|---|---|---|---|
| 01 | 设计 Token + 输入原子 | §01 + §02-A~F | [01-tokens-input-atoms.md](./01-tokens-input-atoms.md) | ~400 |
| 02 | 展示型原子（卡片 / 弹层 / 抽屉 / 反馈） | §02-G~W | [02-display-atoms.md](./02-display-atoms.md) | ~490 |
| 03 | 全局外壳与导航 | §03-A~H | [03-shell-nav.md](./03-shell-nav.md) | ~240 |
| 04 | 聊天 / 引用 / 证据核心（★） | §03-I~O | [04-chat-evidence-citation.md](./04-chat-evidence-citation.md) | ~620 |
| 05 | 知识图谱浏览器 | §03-P~T | [05-kg-canvas.md](./05-kg-canvas.md) | ~480 |
| 06 | 文档库 + 摄取流水线 + 长任务 | §03-U~Z + AA/AB | [06-docs-ingest.md](./06-docs-ingest.md) | ~600 |
| 07 | 推理 / 假设 / 评测 / 设置 | §03-AC~AR | [07-reasoning-eval-settings.md](./07-reasoning-eval-settings.md) | ~710 |
| 08 | 主屏 + Modal + 边界态 + 旅程（整合层） | §04 + §05 + §06 + §07 | [08-screens-modals-states-journeys.md](./08-screens-modals-states-journeys.md) | ~1170 |

总计 ≈ 4700 行规范，覆盖 90 张图全部组件、4 个 Modal、7 种边界态、3 条关键旅程。

---

## 1. 全局不可破红线（贯穿所有子文档）

1. **Citation-first**：任何 LLM 输出必须可追溯到 `citations[]` 中的具体 chunk；渲染期对 `[id]` 做 whitelist 过滤，不在白名单的 chip 静默删除（防 LLM 幻觉污染证据链）。详见 04 §CitationChip。
2. **Library 隔离**：URL 含 `:libraryId` 是数据分区的唯一标志；切库 = `router.push` + `libraryStore.$reset` 广播给所有 lib-scoped store。跨库 URL → 显式 404 + 推荐 3 个最近 library。详见 03 §URL 即状态、08 §跨库误路由。
3. **长任务可后台 / 可断点续 / 可取消**：单 SSE 多 subscriber（`useTaskStream(taskId)`），组件 unmount 不断流；服务端 checkpoint 支持 Resume from section；运行中可"最小化"为右下角 mini pill。详见 06 §单 SSE 多 subscriber、08 §J2。
4. **Budget 是硬墙**：`costStore.exceeded` 时 Chat send / Reasoning generate / Eval run 等 expensive 按钮全部 `disabled` + 显式 tooltip 解释，全局 danger Banner 持久显示，必须改预算后才解锁。详见 07 §CostMeter。
5. **A11y 节流**：流式 `aria-live` 广播节流 ≥ 250 ms；流式中 Composer `aria-busy=true`；Modal/Drawer 嵌套用全局焦点 trap 栈（`useFocusStack`）；focus ring 3 px 永远存在。详见 02 §焦点栈、04 §A11y。
6. **流断不清空**：SSE 断流必须保留已输出 token + 提供 `Continue from here` / `Retry`，不要整条重发。详见 04 §MessageBubble、08 §流式中断。

---

## 2. 跨组件状态机（统一抽象）

### 2.1 异步资源四态（Skeleton / Data / Empty / Error）

由 `useAsyncResource(fetcher, { minVisibleMs, skeletonAfterMs })` 统一管理：

```
loading (≥ skeletonAfterMs 才显示 Skeleton)
  ├─→ data       (≥ minVisibleMs 才允许下一个 loading，防闪烁)
  ├─→ empty      (返回空数组 / null 时走 BaseEmptyState，不是错误)
  └─→ error      (按可恢复性分流到 Inline / Banner / Toast)
```

所有数据面板（DocumentRow / EvidencePanel / KG / Eval / KPI）必须用同一套，避免每屏自己实现导致状态分歧。详见 02 §状态机统一封装。

### 2.2 流式三事件

`event: meta` → `event: token`（× N） → `event: citations` → `event: done | error`

- `meta` 来时：建立消息气泡占位 + token 计数器
- `token` 来时：`useTokenStream` rAF 节流追加 + 智能 autoscroll（用户向上滚 60 px 即停）
- `citations` 来时：把占位 `[?]` chip 实化为编号；whitelist 过滤生效
- `error` 来时：保留已输出 + 显示 Retry chip
- `done` 来时：解除 `aria-busy`，触发首条答案的 onboarding 焦点跳转

### 2.3 长任务进度

`taskStore` 持有 `Map<taskId, TaskState>`；`useTaskStream(taskId)` 按 taskId ref-count 复用 EventSource；PipelineTree / RunStatsSidebar / LiveCitationList / DraftStreamingView 是同一 state 的不同投影。

---

## 3. 全局快捷键 map

| 范围 | 键 | 动作 |
|---|---|---|
| 全局 | `⌘K` / `Ctrl+K` | 打开 CommandPaletteOverlay |
| 全局 | `⌘O` | LibrarySwitcher 弹出 |
| 全局 | `⌘N` | 新建 Library（M1）|
| 全局 | `Esc` | 关闭最顶层浮层（focus stack 决定） |
| 全局 | `g d` | 跳 Documents |
| 全局 | `g c` | 跳 Chat |
| 全局 | `g k` | 跳 KG |
| 全局 | `g e` | 跳 Eval |
| 全局 | `?` | 显示快捷键 cheatsheet |
| Chat | `/` | 聚焦 Composer（在 Chat 外则聚焦顶栏搜索） |
| Composer | `Enter` | 发送 |
| Composer | `Shift+Enter` | 换行 |
| Composer | `⌘Enter` | 强制发送（即使 token 警告） |
| Composer | `Esc Esc` | 清空并保存草稿 |
| Composer | `↑`（空输入时） | 编辑上一条用户消息 |
| Citation | `Tab` / `Shift+Tab` | 在 chip 之间切换焦点 |
| Citation | `Enter` | 跳到对应 EvidenceCard |
| KG | `+` / `-` | 缩放 |
| KG | `f` | fit-to-screen |
| KG | `方向键` | 平移画布 |
| KG | `⌘A` | 全选可见 |
| Table | `j` / `k` | 上下行 |
| Table | `x` | 切换行多选 |

由 `useShortcut(scope)` 实现 scope 隔离（不让 Chat 输入框吃了全局 `/`）。详见 03 §CmdK、04 §Composer。

---

## 4. Pinia store 拓扑

```
libraryStore (root) ──── 触发 $reset 广播 ──┐
  └─ activeLibraryId                       │
                                           ↓
chatStore ─── 引用 ──→ evidenceStore  (lib-scoped)
kgStore ──── 引用 ──→ evidenceStore   (lib-scoped)
taskStore ── 引用 ──→ evidenceStore   (lib-scoped)
                ↓
            colorStore ←─ SchemaEditor 更新 → 广播 KG / PathViz / LibraryCard 热更新

costStore (global) → 拦截 chatStore.send / taskStore.start / evalStore.run
settingsStore (global) → router / embedder / budget / schema
uiStore (global, persisted) → sidenav 折叠 / theme / drawer pin
notificationStore (global) → SSE 通知流
commandPaletteStore (global) → ⌘K 状态、recent、suggestion
```

详见 `FRONTEND_TECH_STACK.md §14`。

---

## 5. Modal / Drawer / Popover / Toast / Banner 决策表

| 场景 | 用 | 理由 |
|---|---|---|
| ≤ 30 s 阻断式任务（建库 / 删库 / 确认） | **Modal** | 必须聚焦 |
| 持续查看 + 主区可继续操作（Evidence / EntityDetail / DocumentDetail） | **Drawer**（可 pin） | pin 后非模态 |
| 临时浏览预览（CitationChip hover、KG 节点 hover、模型卡详情） | **Popover / Tooltip** | 不打断 |
| 临时反馈（操作成功 / 错误）| **Toast**（自动消失） | 短生命周期 |
| 全页持续告警（Budget Exceeded / Worker Offline） | **Banner** | 必须持久可见 |
| 行内字段错误 | **Inline Error** | 紧贴字段 |

详见 02 §Modal vs Drawer 决策树。

---

## 6. 三条关键旅程（参考 08 整合层）

### J1 首次使用 → 第一答案

```
S1 Onboarding (3 cards) → CTA "Create your first Library"
  → M1 LibraryCreateModal (slug 自动 / desc / 主语言)
  → POST /v1/libraries → toast "Library created"
  → router.push(/lib/:id/docs) → DropZone pulse
  → 拖入 PDF → table rows 摄取实时进度
  → 首篇 done → "Now try asking a question" CTA
  → router.push(/lib/:id/chat) → Composer focus + 3 sample question chips
  → 点 chip → SSE → 首条 citation 答案 → 自动打开 EvidencePanel
```

焦点编排：每一步焦点显式移动到下一个 CTA；`?onboarding=1` 串联可分享。

### J2 综述生成长任务

```
S5b 配置 (topic / 章节模板 / depth / reranker / budget)
  → POST /review → taskId → router.push(/lib/:id/review/:taskId)
  → useTaskStream(taskId) 单流多 sub
  → PipelineTree + RunStats + LiveCitationList + DraftStream 同步更新
  → 用户点 "Run in background" → mini pill 右下角悬浮，继续工作
  → server checkpoint 失败 → "Resume from section X" 续写
  → done → toast + 导出 markdown/pdf
```

### J3 KG 探索 → 反馈到 Chat（双向闭环）

```
S4 选 entity A → 右键 "Find paths to..." → 选 entity B
  → router.push(/lib/:id/reason) → cytoscape-dagre 横向路径
  → 点 path 中 chunk → EvidencePanel 高亮
  → "Discuss in Chat" → composerStore.prefill + evidenceStore.pinForNextMessage
  → 跳 chat → 答案 CitationChip 反向高亮 KG 节点（双向闭环）
```

---

## 7. 极易踩坑的细节（已在子文档中标注，集中在此提醒）

1. **CitationChip whitelist 过滤**：渲染期就要做，不能依赖 backend。LLM 编造 `[id]` 时若已渲染到 DOM 再删，会有视觉跳动。
2. **流断保留 token**：很多实现会清空气泡，必须保留 + 提供 Continue。
3. **autoscroll 智能停**：用户向上滚 ≥ 60 px 则停 autoscroll，直到用户回到底再恢复，否则流式写作类产品体验崩。
4. **跨库误路由不静默 redirect**：必须 404 屏 + 推荐 3 库，否则用户以为 URL 被吞。
5. **Drawer pinned 后必须 popTrap + aria-modal=false**：否则 pin 等于失效。
6. **流式 aria-live 必须 ≥ 250 ms 节流** + Composer `aria-busy=true`，否则屏读用户被淹没。
7. **SchemaEditor 颜色更新走 `colorStore` 单一源**：5 ms 内 KG / PathViz / LibraryCard 全部热更新，不要每个组件自己持有色 map。
8. **Embedder 切换必须二次确认**：会触发全库重建索引（消耗大）；BudgetSettingsForm 同理。
9. **`info` token 不要同时承担 Citation 和 Toast 信息态**：拆 `citation-cyan` 与 `neutral-info`，否则引用语义被稀释。
10. **floating-vue 与 Naive 的 z-index 冲突**：在 base 包装层把 `n-popover/n-tooltip` 转译到 floating-vue，长期收敛单一浮层栈。

---

## 8. 与 UI_GALLERY.md 的对应关系

`UI_GALLERY.md` 由 `scripts/generate_ui_images.py` 自动生成，不应手动追加交互文本（每次重跑会被覆盖）。**本文档是其交互伴生文档**：

- 视觉层 → `UI_GALLERY.md`（图）
- 交互层 → 本文档 + `ui-interactions/01–08`（规范）
- 视觉 token + 14 frame 层级 → `FRONTEND_DESIGN_SPEC.md`
- 硬规矩 → `FRONTEND_RULES.md`
- 代码规约 → `FRONTEND_CODING_STANDARDS.md`
- 技术选型 → `FRONTEND_TECH_STACK.md`

阅读路径建议：先 `UI_GALLERY` 看图 → 再本文档定位章节 → 进入对应 `ui-interactions/0X-*.md` 看完整交互细节。
