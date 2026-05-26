# 03 — Shell & Navigation 全局外壳与导航交互规范

> 范围：AppShell（TopBar / SideNav / MiniStats / LibrarySwitcher / Breadcrumb / CmdK Trigger / NotificationBell / I18nSwitcher）。
> 强约束回顾：**URL 即状态**，Library-scoped 页面 URL 必含 `:libraryId`；切库 = `router.push()` + 所有 library-scoped store `reset()`。
> 配色/排版/动效 token 沿用 §01 Cobalt Lab；原子组件来自 §02。

---

## 1. 组件交互规范

### TopBar（024-03-a-topbar）

- **视觉**：固定 64 px 高，背景 `surface/00`（白）+ 底部 1 px `divider/subtle`；左起：品牌 logo `RAG-KG`（cobalt 方块 + 字标）→ `LibrarySwitcher` 按钮 → `Breadcrumb`（中段，flex-grow）→ `CmdK Trigger`（搜索条 240 px）→ `NotificationBell` → `I18nSwitcher` → `UserAvatar`。三种态示意：DEFAULT / WITH-BREADCRUMB / WITH-UNREAD。
- **状态**：默认 / 滚动时阴影态（`scroll-shadow: 0 1px 0 rgba(15,23,42,.06)`，使用 `IntersectionObserver` 监听 sentinel）/ offline 态（顶栏下沿挂 2 px 警告条，i18n key `shell.offline`）。
- **交互**：
  - 整体不参与垂直滚动（`position: sticky; top: 0; z: 30`）。
  - logo 点击 → `router.push({ name: 'workspace.overview', params: { libraryId } })`；若无当前库则跳 `/libraries`。
  - 键盘：`/` 聚焦 CmdK；`⌘K` / `Ctrl+K` 打开命令面板；`⌘O` 打开 LibrarySwitcher；`g d` 跳 Documents（vim-style 两键序列，超时 800 ms 复位）。
- **A11y**：根节点 `role="banner"`；logo 链接 `aria-label="Go to overview"`；当前库名通过 `aria-live="polite"` 在切库时朗读一次。
- **动效**：滚动阴影 fade-in 160 ms `ease-out`；offline 条 slide-down 200 ms。
- **Vue 实现**：
  - 结构：`<AppTopBar>` 内用 CSS Grid `grid-template-columns: auto auto 1fr auto auto auto auto`，所有插槽通过命名 slot 暴露给布局层而非硬编码。
  - 库依赖：`@vueuse/core` 的 `useMagicKeys` 处理 `/` `⌘K` `g d`；`useScroll(window)` 控制阴影；`@unhead/vue` 在切库后更新 `<title>${library.name} · RAG-KG</title>`。
  - 不在此层做业务逻辑，仅通过 `injectionKey` 暴露 `topbarHeight` 给主内容做 sticky 偏移。

#### UI 参数（来自 UI_PROMPTS §03-A）

| 类别 | 值 |
|---|---|
| 容器尺寸 | 1440 × 56（PROMPTS）/ 高度 64（SPEC §1） · 固定顶 |
| 高度 | 56 · `> 冲突：以 SPEC 为准（64）`，CSS Grid 行 `64px 1fr` 不变 |
| padding 左右 | 24 · padding 上下 0 · 内部主轴 gap 16 |
| 背景 | `bg-surface` `rgba(255,255,255,.85)` + backdrop-blur 12 |
| 边框 | 底部 1 px `border-subtle` #E4E4E0 |
| Logo mark | 24 × 24 squircle，填充 `brand-500` #4F46E4，内嵌白色 ◆ 字符 |
| Logo 与字标间距 | 8 |
| 字标 "RAG-KG" | Inter 14 / 700，颜色 `text-primary` #1A1A1A（body 14/16.9） |
| Logo 后到 LibrarySwitcher 间距 | 24 |
| LibrarySwitcher trigger | 240–280 × 32 |
| Breadcrumb | body-sm 13/15.7、`text-tertiary` #8C8C82，分隔 " / " |
| CmdK trigger | 120 × 32（PROMPTS）/ SPEC §1 写 240 ·`> 冲突：以 SPEC 为准（240）` |
| NotificationBell | 32 × 32，未读红点 8、`danger-500` #EE4444 |
| I18nSwitcher | 36 × 32 |
| Avatar | 32 × 32 |
| 右簇排列 | CmdK → Notify → I18n → Avatar（push 至右边缘） |
| 阴影 | 默认无，滚动态 `0 1px 0 rgba(15,23,42,.06)` |
| 动效 | hover/focus 120 ms ease-out · 滚动阴影 fade-in 160 ms · offline 条 slide-down 200 ms |
| z-index | 200（高于 SideNav 100） |

### SideNav（025-03-b-sidenav）

- **视觉**：两种宽度——**Standard 240 px** / **Collapsed 64 px**；分两区 `WORKSPACE`（Overview / Chat / Documents / Knowledge Graph）+ `TASKS`（Review generation / Cross-paper reasoning / Hypothesize / Evaluation）；底部留出 `MiniStatsCard` 槽；Active 项左侧 3 px cobalt 实色 indicator + 行背 `cobalt/04`。
- **状态**：default / hover（行背 `surface/02`）/ active（indicator + bold）/ focus（3 px focus ring，不破坏 indicator）/ collapsed（仅 icon + 黑色 tooltip 右浮）/ collapsed-hover-peek（鼠标停留 320 ms 临时展开为 floating panel，不挤压主内容）。
- **交互**：
  - 切换折叠：⌘\\ 或顶部 chevron；状态写入 `useStorage('shell.sidenav.collapsed', false)`。
  - 字段映射快捷键：`g o` Overview / `g c` Chat / `g d` Documents / `g k` Knowledge Graph / `g t` Tasks 首项。
  - 路由 active 不再用 `isActive` 字符串比对，统一用 `RouterLink` 的 `:to` + `activeClass` + `exactActiveClass`，并对子路由用 `aria-current="page"`。
- **A11y**：根节点 `role="navigation" aria-label="Primary"`；分区使用 `<ul role="list">` + 视觉上的 `WORKSPACE / TASKS` 用 `<h2>` 视觉 hidden（`sr-only`）；collapsed 态 tooltip 用 `aria-describedby` 关联，禁止使用 `title` 属性（移动端不可读）。
- **动效**：宽度变化 `transition: width 200ms cubic-bezier(.2,.8,.2,1)`；hover-peek 进入 180 ms `ease-out`，离开 120 ms；`prefers-reduced-motion` 时关闭 peek。
- **Vue 实现**：
  - 推荐：`@formkit/auto-animate` 用于子项展开（Tasks 区可折叠）；`floating-vue` 提供 collapsed 态 tooltip（已支持 `aria` 转发）。
  - 路由表用单一 `navConfig.ts` 维护，含 `icon / labelKey / to / shortcut / matchRegex`；SideNav 与 CmdK 共用，避免双写。

#### UI 参数（来自 UI_PROMPTS §03-B）

| 类别 | 值 |
|---|---|
| 容器尺寸（展开） | 240 × 844（满高 - topbar）· 折叠 64 |
| 背景 | `bg-surface` #FFFFFF |
| 边框 | 右侧 1 px `border-subtle` #E4E4E0 |
| 内 padding | 16 |
| 分组 label "WORKSPACE" / "TASKS" | meta 11/13.3 / 500 uppercase，颜色 `text-tertiary` #8C8C82，padding 8/8 |
| 分组间距 | WORKSPACE → TASKS 16；TASKS → MiniStats 24 |
| Nav item 尺寸 | 216 × 36，radius 10，padding 0/12，内部 gap 8 |
| Nav item 文本 | body-sm 13/15.7 / 600，颜色 `text-secondary` #515151 |
| Leading icon | 16，Lucide stroke 1.5 |
| Active 行 | bg `brand-50` #EDF0FF，文本 `brand-700` #2A1FAF，icon `brand-500` #4F46E4 |
| Active 指示条 | 3 × 28，`brand-500` #4F46E4，贴左边缘垂直居中 |
| Hover 行 | bg `bg-subtle` #F4F4F1 |
| MiniStatsCard 槽位 | 216 × 180，置底 |
| 折叠态宽度 | 64，仅 icon，hover tooltip 弹出 label |
| 折叠按钮快捷键 | ⌘\ |
| Hover-peek 延迟 | 进入 320 ms，浮出 180 ms ease-out，离开 120 ms |
| 折叠动效 | width 200 ms cubic-bezier(.2,.8,.2,1) |
| z-index | 100 |

### SideNav MiniStatsCard（026-03-c）

- **视觉**：圆角 12 px 卡片，标题行为 `●` 颜色点 + 库名（粗体）；正文两行：`{docs} docs · {chunks} chunks` / `{entities} entities · {triples} triples`；分隔线下方蓝色文字链 `Open Library settings →`。
- **状态**：loaded / loading（用 §02 Skeleton 三条占位）/ stale（数字旁挂 §02 StatusPill `stale`，配 §05 toast 引导 reindex）/ error（折叠为单行错误 + retry 文本按钮）。
- **交互**：
  - 数字 hover 显示 §02 Tooltip：`Last updated 5m ago · Click to refresh`；点击触发 `libraryStatsStore.refresh()`，使用 SWR：先返旧值再请求。
  - `Open Library settings →` → `router.push({ name: 'library.settings' })`，保留当前 `libraryId`。
  - collapsed 态退化为单一 `📊` IconButton，点击弹同尺寸 Popover。
- **A11y**：`role="region" aria-label="Library statistics"`；数字单独 `aria-label="documents: 2,184"` 防止读屏拼读。
- **动效**：数字变化用 `@vueuse/core` `useTransition` 做 400 ms tween；颜色点 `pop-in` 120 ms。
- **Vue 实现**：`pinia` 中 `libraryStatsStore` 按 `libraryId` 缓存；切库时由 `libraryStore.$onAction` 监听 `setActive` 主动 invalidate。

#### UI 参数（来自 UI_PROMPTS §03-C）

| 类别 | 值 |
|---|---|
| 卡片尺寸 | 216 × 180 |
| 圆角 | 14（PROMPTS）/ SPEC §1 写 12 ·`> 冲突：以 SPEC 为准（12）` |
| 背景 | `bg-subtle` #F4F4F1 |
| padding | 16 |
| 顶部颜色点 | 8，色取自 Library hash，默认 `brand-500` #4F46E4 |
| 库名（slug） | body-sm 13/15.7 / 600 |
| 正文 2 行 | body-sm 13/15.7 / 400，颜色 `text-secondary` #515151；示例 `2,184 docs · 62.4k chunks`、`8,491 entities · 31.2k triples` |
| 分隔线 | 1 px `border-subtle` #E4E4E0 |
| Footer 链接 | "Open Library settings →" body-sm 13 / 600，颜色 `brand-600` #3B30D9 |
| 数字字体特性 | tabular-nums |
| 趋势 chip 颜色 | — |
| 动效 | 数字 tween 400 ms，颜色点 pop-in 120 ms |

### LibrarySwitcher ★（027-03-d）

- **视觉**：Trigger 是带 `●` 颜色点 + 库名 + `chevron-down` 的胶囊按钮（在 TopBar 内）。展开为 ≈320 × 380 px 浮层：顶部 Search 输入（`Search libraries…`）→ `PINNED` 区（最多 5 条，左对齐颜色点 + 名称，右对齐 docs 计数）→ `RECENT` 区（最近 5 条）→ 底部主按钮 `+ New Library`，最下方一行键位提示 `↑↓ navigate · ↵ open · ⌘N new`。
- **状态**：closed / open / searching（去抖 120 ms 过滤）/ empty-search（§02 EmptyState「No libraries matching "x"」+ CTA `+ Create "x"`）/ pending-switch（行右侧出现 §02 Spinner）。
- **交互（重点）**：
  - 打开：⌘O 或点击 trigger。
  - 键盘：`↑/↓` 在合并列表（pinned + recent，跳过分组标题）移动 `aria-activedescendant`；`Enter` 切库；`⌘N` 新建；`Esc` 关闭；`Tab` 在搜索框 → 列表 → 新建按钮 → 列表（loop）。
  - 切换前若当前页有未提交编辑（`chatStore.hasDraft || composerStore.dirty`），先弹 §02 Modal `Discard draft?`。
  - 切换成功 → `router.push({ name: route.name, params: { libraryId: next.id }})`（保留当前 route name，跨库重放路径）→ 所有 `library-scoped` store 调用 `reset()`（约定钩子：每个 store 暴露 `reset()`，由 `libraryStore.$onAction('setActive', ...)` 广播）→ §02 Toast `Switched to ${next.name}`，提供 `Undo` 5 s（点击回滚到旧 libraryId）。
  - Pin/Unpin：行 hover 出现 `📌` IconButton；右键菜单（`floating-vue` ContextMenu）含 `Pin / Rename / Open in new tab / Delete…`。
  - 搜索匹配使用 `fuse.js`（字段：name, slug, tags），高亮匹配片段（`<mark>`）。
- **A11y**：trigger `aria-haspopup="listbox" aria-expanded` ；浮层 `role="dialog" aria-modal="false" aria-label="Switch library"`；搜索框 `role="combobox" aria-controls="lib-listbox"`；列表 `role="listbox"` + 每项 `role="option" aria-selected`；键位提示行 `role="status"`。
- **动效**：浮层 fade+scale-from-95 200 ms `ease-out`；分组标题 `auto-animate` 在筛选时折叠；切库时整层 dissolve 160 ms。
- **Vue 实现**：
  - 浮层：`floating-vue` 的 `Dropdown`（`triggers: ['click']`，`auto-hide`）+ 自管 `focusTrap`（`focus-trap` 包）。
  - 列表过渡：`@formkit/auto-animate`。
  - 命令收集：`useMagicKeys({ passive: false })`，`⌘+o` 调 `libSwitcher.open()`，`⌘+shift+l` 调 `libSwitcher.create()`。
  - 路由：用 `@vueuse/router` `useRouteParams('libraryId')` 与 `libraryStore.activeId` 双向绑定但**以 URL 为唯一真源**——store 仅作 setter 触发副作用，不持久化。

#### UI 参数（来自 UI_PROMPTS §03-D）

| 类别 | 值 |
|---|---|
| Trigger 尺寸 | 240–280 × 32，radius 10 |
| Trigger 背景 | `bg-surface` #FFFFFF，1 px `border-default` #D3D3CE |
| Trigger padding | 4 / 10 |
| 颜色点 | 12 × 12（取库 hash 色，默认 `brand-500` #4F46E4） |
| Slug 文本 | body-sm 13/15.7 / 600，颜色 `text-primary` #1A1A1A |
| Caret | "▾" 12，颜色 `text-tertiary` #8C8C82 |
| Trigger hover | bg `bg-subtle` #F4F4F1 |
| Trigger focus | ring `brand-500` 3 px `rgba(79,70,229,.20)` |
| Popover 面板尺寸 | 320 × 420（PROMPTS）/ SPEC §1 约 320 × 380 ·`> 冲突：以 SPEC 为准（320 × 380）` |
| Popover radius | 14 |
| Popover shadow | `lg` `0 12px 32px rgba(15,15,20,.10)` |
| Section header（PINNED / RECENT） | meta 11/13.3 / 500 uppercase，颜色 `text-tertiary` #8C8C82 |
| Search 输入高度 | 36，placeholder "🔍 Search libraries…" |
| 每项行 | 行内 dot + slug + 右对齐统计；活动行 bg `brand-50` #EDF0FF |
| 行内统计字号 | mono 13/20，颜色 `text-tertiary` #8C8C82（JetBrains Mono） |
| "+ New Library" 行 | plus icon `brand-600` #3B30D9 + body-sm 13 / 600 |
| 键位 hint footer | "↑↓ navigate  ↵ open  ⌘N new"，caption 12/14.5 / 400 |
| 动效 | fade+scale-from-95 200 ms ease-out，切库 dissolve 160 ms |
| z-index | 1000（floating-vue 默认） |

### Breadcrumb（028-03-e）

- **视觉**：`Workspace / graphrag-survey / Chat / Session 2026-05-05`；分隔符 `/` 6 px 横向 padding，`text-tertiary`；末段为当前页（`text-secondary 600 / body-sm`），可选择 + 复制。
- **层级规则**：永远三段不可省 + 末段动态：
  1. `Workspace`（点击回 `/libraries/:id`）
  2. `{library.name}`（颜色点 + 名称，hover 弹与 LibrarySwitcher 同源的浮层；点击 = 打开 LibrarySwitcher，定位到当前库）
  3. `{section}` (Chat / Documents / Knowledge Graph / Tasks / Settings)
  4. `{resource?}` (Session date, Document title, Entity name) — 可缺。
- **状态**：normal / truncated（总宽 < 480 px 时中段折叠为 `…`，点击展开为 §02 Popover 列出被折叠的若干段）/ root（仅 `Workspace`）/ loading（每段 §02 Skeleton chip）。
- **交互**：
  - 段点击 → `router.push`，**不携带 query**（避免泄漏过滤态到上级）。
  - `⌘[`(Mac) / `Alt+←`(Win) 后退到上一段；`⌘.` 复制末段文本。
  - 移动端（< 640 px）：默认折叠至 `… / 末段`，点击 `…` 出竖排 Popover。
- **A11y**：根节点 `<nav aria-label="breadcrumb">`；末段 `aria-current="page"`；折叠按钮 `aria-label="Show hidden breadcrumb segments"`。
- **动效**：路由切换时新末段 `fade-in 120ms`，旧末段不做 out 动画（避免抖动）。
- **Vue 实现**：
  - 数据源：每个路由的 `meta.breadcrumb = (route) => Promise<Segment[]>`，由 `useBreadcrumb()` composable 合成；library 段从 `libraryStore` 取，resource 段由各页面在 `onMounted` 注册（`provideBreadcrumbTail`）。
  - 不直接读 `route.matched`，因为 RAG 业务中"section + resource"经常跨 nested route，集中由 composable 计算更稳。

#### UI 参数（来自 UI_PROMPTS §03-E）

| 类别 | 值 |
|---|---|
| 排列 | 单行 inline row |
| 文本字号 | body-sm 13/15.7 / 400，颜色 `text-tertiary` #8C8C82 |
| 末段（active） | body-sm 13/15.7 / 600，颜色 `text-secondary` #515151，`aria-current="page"` |
| 分隔符 | " / "（middot/slash），左右各 6 padding |
| 中段截断 | 总宽 > 480 时中段折叠为 "…" |
| Hover 下划线 | 仅可点击段，hover 时 underline，120 ms ease-out |
| 移动端折叠阈值 | < 640，折叠为 `… / 末段` |
| 单段最大字符 | 24，超出中间省略 |
| 字体 | Inter（PingFang SC 中文回退） |
| 动效 | 新末段 fade-in 120 ms |

### CmdK Search Trigger（029-03-f）

- **视觉**：圆角 8 px、240 px 宽的 placeholder 输入条；左 `search` 图标 + `Search…` 文案，右一颗 `⌘K` 键帽（`kbd` 风格，1 px 边 + 渐变）。本身**不是**真输入框，仅触发器。
- **状态**：default / hover（边框 cobalt/40）/ focus（focus ring，由 Tab 到达时也可 Enter 打开）/ press（轻微下沉 1 px）。
- **交互**：
  - 点击 / Enter / `⌘K` / `Ctrl+K` / `/` → 触发全局事件 `cmdk:open`，由 §05 CommandPaletteOverlay 接管。
  - 右侧键帽在 macOS 显示 `⌘K`，Windows/Linux 显示 `Ctrl K`，运行时通过 `navigator.userAgentData.platform` 判定。
  - Esc 仅在 Overlay 打开时生效（trigger 自身不消费 Esc，避免拦截其它面板）。
- **A11y**：`role="button" aria-haspopup="dialog" aria-keyshortcuts="Meta+K Control+K"`；不要用真 `<input>`，否则 NVDA 会朗读"edit"误导用户。
- **动效**：press 50 ms；hover 边框 120 ms。
- **Vue 实现**：纯展示组件 `<CmdKTrigger />`，仅 emit `open`；快捷键全局监听放在 `AppShell.vue` 的 setup 中（`useMagicKeys`），避免组件重复挂监听导致双触发。

#### UI 参数（来自 UI_PROMPTS §03-F）

| 类别 | 值 |
|---|---|
| 容器 | 120–200 × 32（PROMPTS）/ SPEC §1 写 240 ·`> 冲突：以 SPEC 为准（240）` |
| radius | 10（PROMPTS）/ SPEC §1 写 8 ·`> 冲突：以 SPEC 为准（8）` |
| 背景 | `bg-subtle` #F4F4F1，无边框 |
| padding | 0 / 10 |
| 左侧 search icon | Lucide search 14，颜色 `text-tertiary` #8C8C82 |
| placeholder | "Search…" body-sm 13/15.7 / 400，颜色 `text-tertiary` #8C8C82 |
| 右侧 ⌘K chip | 22 × 18，bg `bg-surface` #FFFFFF，1 px `border-subtle` #E4E4E0，字体 JetBrains Mono 13/20 / 600 |
| Hover | bg `bg-muted` #EAEAE5 |
| Press | 下沉 1 px，50 ms |
| 动效 | hover 边框 120 ms ease-out |

### NotificationBell（030-03-g）

- **视觉**：IconButton（铃铛），右上角红点徽章（无数字，仅状态），点击展开 ≈360 × 440 px Popover：标题 `Notifications` + `Mark all read`；列表条目 = `状态色左条 + icon + 标题 + 副标题（library/scope）+ 相对时间`；底部 `Open notification center →`。
- **状态**：no-unread（无红点）/ has-unread（红点 `pop-in 120ms`，数量 ≥ 1 时仅显示点，鼠标 hover 显示 `aria-label="3 unread notifications"`）/ open / loading / error / empty（§02 EmptyState `You're all caught up`）。
- **交互**：
  - 点击 trigger 打开 Popover（**Popover 而非 Drawer**——理由见议题 §2.5）；移动端 < 768 px 才降级为底部 Drawer。
  - 条目点击：导航到目标资源（如 `library/:id/tasks/:taskId`），同时把该条标为 read（`PATCH /notifications/:id`）。
  - `Mark all read` 触发批量 `POST /notifications/read-all`，乐观更新 + 失败回滚。
  - 与全局 Toast 系统去重：每条通知带 `dedupeKey = type + resourceId`，若过去 60 s 内已 toast 同 key，则只更新 bell 列表不再 toast。
  - 快捷键：`g n` 跳通知中心；`Shift+N` 切换 Popover。
- **A11y**：trigger `aria-label="Notifications, {n} unread"` 动态更新；红点本身 `aria-hidden`；Popover `role="dialog" aria-modal="false"`；未读数变化用 `<span role="status" aria-live="polite" class="sr-only">` 通告。
- **动效**：红点 pop-in 120 ms cubic-bezier(.34,1.56,.64,1)；Popover scale-from-95 200 ms。
- **Vue 实现**：
  - 实时通道：**首选 SSE**（`EventSource` to `/api/v1/notifications/stream`），失败自动降级到 30 s 轮询（`@vueuse/core` `useIntervalFn`）。
  - Store：`notificationsStore` 维护 `items / unreadCount / connectionState`；SSE 收到事件 → push + 触发 toast 去重判断。
  - Popover：`floating-vue` + `auto-animate` 列表入场。

#### UI 参数（来自 UI_PROMPTS §03-G）

| 类别 | 值 |
|---|---|
| IconButton | 32 × 32，Lucide bell 18，stroke 1.5 |
| 未读红点 | 8 × 8，`danger-500` #EE4444，右上角，外层 12 padding 的 `bg-surface` #FFFFFF halo |
| Popover 尺寸 | 360 × 420（PROMPTS）/ SPEC §1 约 360 × 440 ·`> 冲突：以 SPEC 为准（360 × 440）` |
| Popover 锚点 | 铃下方 |
| Header 文本 | "Notifications" body 14/16.9 / 600 |
| "Mark all read" ghost | body-sm 13/15.7 / 400 |
| 通知行高 | 64 |
| 状态 icon | 20 × 20，semantic 50 背景色（success/info/warning/danger） |
| 行标题 | body-sm 13/15.7 / 600 |
| 行 meta | body-sm 13/15.7 / 400，`text-tertiary` #8C8C82 |
| 相对时间 | caption 11/13.3 / 500，右对齐 |
| 未读左指示条 | 4 × 全行，`brand-500` #4F46E4 |
| Footer 链接 | "Open notification center →" body-sm 13 / 600，`brand-600` #3B30D9 |
| 动效 | 红点 pop-in 120 ms cubic-bezier(.34,1.56,.64,1)；Popover scale-from-95 200 ms |

### I18nSwitcher（031-03-h）

- **视觉**：胶囊按钮 `EN ⌄` / `中 ⌄`，展开为 ≈140 × 80 px 列表 `English` / `中文`，当前项前置 `✓`。
- **状态**：default / open / switching（短暂 spinner，等异步加载新 locale 包）。
- **交互**：
  - 点击切换 → `i18n.global.locale.value = next`，**无需 reload**（前提：所有运行时字符串都走 `t()`，无构建期硬编码；详见议题 §2.6）。
  - 同步副作用：`document.documentElement.lang = next`；`document.documentElement.dir = 'ltr'`（保留扩展位）；持久化 `useStorage('shell.locale', next)`；通知 `dayjs.locale(next)` 和 `Intl.NumberFormat`（封装在 `useFormat()` composable）。
  - 切换后 §02 Toast：`Switched to 中文 · Undo`。
  - 快捷键不分配（避免与 IME 冲突）。
- **A11y**：`role="menu"`；选项 `role="menuitemradio" aria-checked`；trigger `aria-label="Change language, current English"`。
- **动效**：列表 fade+scale 160 ms。
- **Vue 实现**：
  - `vue-i18n` 9.x composition API；按需 `import.meta.glob('./locales/*.json', { import: 'default' })`，惰性加载。
  - 缺失 key 策略：开发环境 `missingWarn: true` 红字回退；生产环境回退到 `en` 并上报 `missing-i18n` 事件到 Sentry/自有日志，**永不显示 raw key**。

#### UI 参数（来自 UI_PROMPTS §03-H）

| 类别 | 值 |
|---|---|
| Trigger 尺寸 | 36 × 32，ghost（无 bg / 无边框） |
| Trigger 文本 | "EN ▾" body-sm 13/15.7 / 600，颜色 `text-secondary` #515151 |
| Popover 尺寸 | 120 × 96（PROMPTS）/ SPEC §1 约 140 × 80 ·`> 冲突：以 SPEC 为准（140 × 80）` |
| Popover radius | 10 |
| Popover shadow | `md` `0 4px 12px rgba(15,15,20,.06)` |
| 列表项 | "English"（active，前置 ✓） / "中文"（inactive） |
| 当前项高亮 | 前置 ✓（无背景色） |
| 持久化 | localStorage |
| 动效 | fade + scale 160 ms |
| 快捷键 | 不分配（避免与 IME 冲突） |

---

## 2. 重点议题

### 2.1 LibrarySwitcher 三段式列表（仿 GH/Vercel）

- 结构顺序：**Search → Pinned → Recent → + New**（中间分隔线 1 px `divider/subtle`，分组标题 `text-tertiary text-xs uppercase`）。
- 数据规则：
  - `Pinned`：用户显式 pin，最多 5 个；存 `userPrefsStore.pinnedLibraryIds[]`，按用户排序，可拖拽（`@formkit/auto-animate` + `vue-draggable-plus`）。
  - `Recent`：从 `libraryStore.recentIds`（LRU，max 8）过滤掉 pinned。
  - 搜索激活时，Pinned/Recent 合并成单一过滤列表，仍优先排序 pinned。
- 键盘地图：
  - `⌘O` 打开 / `Esc` 关闭。
  - `↑/↓` 在合并列表移动（跳过 group header）。
  - `Enter` 切库；按住 `⌘+Enter` 在新标签打开（`window.open` 同源新页）。
  - `⌘N` 创建新库 → 打开 §05 `LibraryCreateModal`，关闭 switcher。
  - `⌘+Shift+L` 直接打开 create modal（即使 switcher 未开）。
  - 输入框中 `Backspace` 在为空时不关闭面板（防误关）。
- 状态机：`closed → opening → open → searching/idle → switching → closed`；`switching` 阶段禁止再次按 Enter（防双跳）。
- 与路由：**切库永远 push 而非 replace**（保留历史，便于 `⌘[` 回退）。

### 2.2 Breadcrumb 语义化与移动端降级

- **总是显示** `Workspace / {library} / {section}`，三段为契约层；第四段 `{resource}` 可选。
- 中段省略策略：测量容器宽度（`useResizeObserver`），当总宽 < 480 px 时把"中间段"折叠为 `…`，**首段（Workspace）与末段永不省略**，符合 ARIA breadcrumb 最佳实践。
- 点击 `…` 弹竖排 Popover 列出隐藏段；触屏长按则替代 hover。
- 库段是"双触发"：左键直跳 library overview；右键 / 长按 = 打开 LibrarySwitcher 浮层，重用同一组件实例（通过事件总线 `bus.emit('libSwitcher:open', { anchor })`）。
- 文本不可换行（`white-space: nowrap`），但单段超 24 字时中间省略 `library-with-very-l…ng-name`。

### 2.3 SideNav 折叠态

- **是否 sticky**：sticky 但不全局——SideNav 与 TopBar 共享一个 sticky 上下文（`position: sticky; top: 0; height: calc(100vh - 64px)`），随主内容垂直滚动条独立滚动其内部 Tasks 区。
- Hover 临时展开（peek）：进入 320 ms 延迟后展开为 `position: fixed` 浮层，**不挤压主 grid**；离开 120 ms 收回；`prefers-reduced-motion` 时禁用 peek，按键盘仍可展开。
- 持久化：`useStorage('shell.sidenav.collapsed', false, localStorage, { mergeDefaults: true })`；浏览器宽度 < 1024 px 时强制初始 collapsed=true，但不写回 storage。
- 与主内容协作：AppShell 用 CSS Grid `grid-template-columns: var(--side-w) 1fr`，`--side-w` 由 root data attribute 控制（`data-sidenav="standard | collapsed"`），避免 JS 写内联样式触发重排。

### 2.4 CmdK 触发器的视觉提示

- TopBar 内始终显示 `⌘K` 键帽，作为"应用主入口"的视觉锚点；移动端隐藏键帽，保留搜索图标。
- trigger 与 Overlay 解耦：trigger 只 emit `cmdk:open`，Overlay 由 §05 单例挂载在 `<body>` 直接子节点，避免被 SideNav 的 `transform` 截断 fixed 定位。
- 视觉提示策略：首次访问用户在 trigger 右侧挂一个 §02 Tooltip `Try ⌘K — global search`，3 s 自动消失，写 flag 到 `userPrefsStore.hints.cmdkSeen`。

### 2.5 NotificationBell 实时性 / 已读策略 / 形态选择

- **传输**：**SSE > 轮询**——理由：单向、低开销、原生重连；后端已支持 `/notifications/stream`。降级链：SSE → 30 s 轮询（手动可见性变化时立即拉一次）。WebSocket 留给 §07 Chat 流式输出使用，避免与通知共用通道引入复杂订阅模型。
- **已读策略**：双状态 `seen`（Popover 打开即批量标 seen，清除红点）与 `read`（点击具体条目才 read）。`seen` 仅影响徽章；`read` 影响列表样式。
- **形态**：桌面端用 **Popover**（轻量，不抢主内容焦点）；移动端 < 768 px 降级为底部 `Drawer`（§02 BaseDrawer，`placement="bottom"`）。Drawer 适用于通知中心整页，但 bell 入口应保持轻量。
- **去重**：notificationsStore 维护 `recentToastKeys: Map<string, timestamp>`，60 s 滑窗，重复事件仅更新 bell 列表，避免 toast 风暴。

### 2.6 I18nSwitcher 切换是否 reload + 缺失 key 策略

- **不 reload**：vue-i18n 9 是响应式的；所有 UI 文本走 `t()`，所有日期/数字走 `useFormat()`（内部根据 `locale` 切 `dayjs` 与 `Intl`），切换即时生效。
- 例外：若加载的 locale 含**新增的路由 meta title 翻译**，则当前页 `<title>` 用 `@unhead/vue` 的 `useHead({ title: () => t('...') })` 自动重算；无需 reload。
- DOM 属性：`document.documentElement.lang = locale`；为未来阿拉伯语预留 `dir` 占位但当前固定 `ltr`。
- 数字/日期：禁止业务代码直接 `new Date().toLocaleString()`，统一封装；服务端返回 ISO 8601，前端格式化。
- **缺失 key**：
  - 开发：`vue-i18n` 配置 `missingWarn: true, fallbackWarn: true`，控制台醒目红字。
  - 生产：`missing` handler → fallback 到 `en` → 仍缺失则返回 `key.split('.').pop()` 的 humanized 形式（如 `library.settings.title` → "Title"），并上报 `i18n.missing` 事件，**永不裸露 dotted key**。

---

## 3. AppShell.vue Grid 与 Slot 拆分

```
┌──────────────────────────────────────────────────────────────────────┐
│ AppShell.vue                                                         │
│ data-sidenav={standard|collapsed}                                    │
│ grid-template-rows: 64px 1fr                                         │
│ grid-template-columns: var(--side-w) 1fr   (--side-w: 240 / 64)      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ <AppTopBar> (grid-area: 1 / 1 / 2 / 3)                       │    │
│  │  slots: #brand  #librarySwitcher  #breadcrumb                │    │
│  │         #cmdk   #bell   #i18n   #avatar                      │    │
│  └──────────────────────────────────────────────────────────────┘    │
│  ┌────────────┐  ┌──────────────────────────────────────────────┐    │
│  │ <AppSideNav>  │  <main role="main">                          │    │
│  │  slot:#nav │  │   <RouterView v-slot="{ Component }">        │    │
│  │  slot:#stats│ │     <Suspense> <component :is="Component"/>  │    │
│  │            │  │     </Suspense>                              │    │
│  │  (sticky)  │  │   </RouterView>                              │    │
│  │            │  │  <PortalTarget name="page-actions" />        │    │
│  └────────────┘  └──────────────────────────────────────────────┘    │
│                                                                      │
│  <Teleport to="body">  ← CommandPaletteOverlay / Toaster / Modals   │
└──────────────────────────────────────────────────────────────────────┘
```

- `AppShell` 不感知业务，只提供 grid + slot + 全局快捷键挂载点。
- 路由守卫 `beforeEach` 中：若目标路由 `meta.libraryScoped === true` 且缺 `:libraryId` → redirect 到 `libraryStore.lastActiveId || /libraries`；切换 `libraryId` 时由 `libraryStore.$onAction` 广播给所有订阅 store 调 `reset()`。
- `<Suspense>` 包裹主内容，配合每个页面顶部的 `<PageSkeleton />` 替代默认 fallback。

---

## 4. 三条全局外壳不可破规范

1. **URL 是唯一真源**：`libraryId / sessionId / documentId` 必须出现在 URL；任何 store 状态切换都先 `router.push`，再由路由守卫驱动 store；禁止 store → URL 的反向流。违反者会让"分享链接"和"浏览器前进/后退"失效。
2. **TopBar 与 SideNav 高度永久固定（64 / 100vh-64）且使用 CSS Grid 行列变量**：任何业务页面禁止用 `position: fixed` 自建悬浮顶/侧栏，必须通过 `<Teleport>` 投递到 `AppShell` 的命名 slot（`page-actions`、`secondary-nav`）。这是为了让 CmdK Overlay、Toast、Drawer 的 z-index 与 focus trap 始终可预测。
3. **所有快捷键集中注册在 `AppShell.setup()`**：业务组件需要快捷键时通过 `useShortcut('g d', handler, { scope: 'documents' })` 注册，由 AppShell 持有的中央 dispatcher 根据当前路由 `scope` 决定是否触发。禁止在叶子组件直接 `window.addEventListener('keydown')`，否则会出现重复触发、IME 误吞、Modal 内泄漏等不可控问题。

---

## 5. 与 §02 原子 / §05 Overlay 的接口

- LibrarySwitcher Popover、NotificationBell Popover、I18nSwitcher Menu 全部基于 §02 `BasePopover` + `floating-vue` middleware（offset 8 / flip / shift）。
- 切库提示、i18n 切换提示走 §02 Toast `useToast()`，支持 `actions: [{ label: 'Undo', onClick }]`。
- CmdK Trigger 仅触发 §05 `CommandPaletteOverlay`，本层不持有 overlay 状态。

---

## 6. AppShell Grid 精确参数表

> 取值规则：以 SPEC §1（本文档主体）为准；PROMPTS 取到的与 SPEC 冲突的数字仅在组件章节中标注。

| 区域 | 高 / 宽 | 背景 | 边框 | z-index |
|---|---|---|---|---|
| TopBar | 高 64 | `bg-surface` #FFFFFF（实色）/ 滚动时 `rgba(255,255,255,.85)` + backdrop-blur 12 | 底 1 px `border-subtle` #E4E4E0 | 200 |
| SideNav 展开 | 宽 240 · 高 `calc(100vh - 64px)` | `bg-surface` #FFFFFF | 右 1 px `border-subtle` #E4E4E0 | 100 |
| SideNav 折叠 | 宽 64 · 高 `calc(100vh - 64px)` | `bg-surface` #FFFFFF | 右 1 px `border-subtle` #E4E4E0 | 100 |
| SideNav peek（hover 浮出） | 宽 240 · 同上 | `bg-surface` #FFFFFF + `shadow-md` `0 4px 12px rgba(15,15,20,.06)` | 1 px `border-subtle` | 150（高于 sidenav，低于 topbar） |
| Main | `1fr × 1fr` | `bg-canvas` #FAFAF9 | — | 0 |
| MiniStatsCard 槽位 | 216 × 180，置 SideNav 底 | `bg-subtle` #F4F4F1 | — | 0（嵌于 SideNav） |
| CommandPalette Overlay | 视口居中，max 720 | `bg-surface` + `shadow-lg` `0 12px 32px rgba(15,15,20,.10)` | 1 px `border-subtle` | 1000（Teleport to body） |
| Toaster | 视口右下 | 透明容器 | — | 1100 |
| Modal | 视口居中 | `bg-surface` + `shadow-lg` | — | 1200 |

### Grid 模板（AppShell.vue 根）

| 属性 | 值 |
|---|---|
| `grid-template-rows` | `64px 1fr` |
| `grid-template-columns` | `var(--side-w) 1fr` |
| `--side-w` 默认 | `240px`（`data-sidenav="standard"`） |
| `--side-w` 折叠 | `64px`（`data-sidenav="collapsed"`） |
| TopBar grid-area | `1 / 1 / 2 / 3` |
| SideNav grid-area | `2 / 1 / 3 / 2` |
| Main grid-area | `2 / 2 / 3 / 3` |
| 列宽变更过渡 | `width 200ms cubic-bezier(.2,.8,.2,1)` |
| 行高 | 锁定 64，禁止业务页面改动 |

### 全局间距 / Radius 约束（沿用 §01 Cobalt Lab）

| 类别 | 值 |
|---|---|
| Spacing 基数 | 4 |
| 间距阶 | 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64 |
| Grid 主内容 | 12-column · gutter 24 · max-width 1280 · side-safe 32 |
| Radius | chip 6 · button/input 10 · card 14 · modal 20 · pill 999 |
| Shadow sm | `0 1px 2px rgba(15,15,20,.04)` |
| Shadow md | `0 4px 12px rgba(15,15,20,.06)` |
| Shadow lg | `0 12px 32px rgba(15,15,20,.10)` |
| Focus ring | `0 0 0 3px rgba(79,70,229,.20)` |
| 全局动效基线 | hover/focus 120 ms ease-out · modal 200 ms cubic-bezier(.2,.8,.2,1) · page 240 ms ease |
