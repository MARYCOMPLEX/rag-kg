# 02 · 展示型原子组件 · 交互规范

> Cobalt Lab × RAG-KG Copilot · Vue 3.4 + Naive UI + UnoCSS
> 适用范围：`components/base/*`（业务层只能消费包装件，不直接吃 `n-*`）
> 关联设计图：`docs/ui-images/008…023-*.png`
> 关联前置：`01-form-atoms.md`（输入/按钮）；后置：`03-domain-organisms.md`（领域组件）

---

## 0 · 全局公约（覆盖本档所有组件）

| 项 | 规范 |
|---|---|
| 圆角 | chip 6 / button 10 / card 14 / modal 20 / pill 999 |
| 动效 | hover 120 ms ease-out · modal/drawer 200 ms cubic-bezier(.2,.8,.2,1) · 进入/退出曲线一致 |
| 缩减动效 | 必须接 `@media (prefers-reduced-motion: reduce)` 与 `useReducedMotion()`（@vueuse/core）双护栏 |
| z-index 段位 | base 0 · sticky 100 · dropdown 1000 · drawer 2000 · modal 3000 · popover 3100 · tooltip 3200 · toast 4000 |
| 焦点环 | 统一 `outline: 2px solid #4F46E4; outline-offset: 2px;`，禁止只用颜色暗示 |
| 文案 | 所有 user-facing 字串走 `vue-i18n` key，禁止裸字面量 |
| Provide-Inject Symbol | `BaseTabsSymbol` / `BaseModalStackSymbol` / `BaseToastSymbol`，常量集中放 `components/base/_symbols.ts` |

---

## 1 · BaseCard（008）

- **视觉**：白底卡片，14 px 圆角；两种 variant：`bordered`（1 px `#E4E4E0`）与 `elevated`（无边、阴影 `0 1px 2px rgba(15,15,20,.06)`，hover 抬到 `0 4px 12px rgba(15,15,20,.08)`）。结构固定：图标 + Header（meta）/ Body（摘要）/ Footer（行为）。
- **状态**：`default` · `hover`（仅 elevated 抬阴影 + 微 -1 px translateY）· `focused`（键盘）· `selected`（左边 2 px brand 条 / 整卡 1 px brand 描边）· `loading`（内容替换为 Skeleton）· `disabled`（opacity 60 % + cursor not-allowed）。
- **交互**：整卡可点（`role="link"` 时）则整卡 hit-area；卡内含次级 action 时整卡禁止可点，避免点击穿透。键盘：`Enter/Space` 触发主 action；`Tab` 应只停在主 action 而非整卡（避免双焦点）。
- **A11y**：可点卡用 `<a>`/`<button>` 包裹，不要 `div + onClick`；纯展示卡 `role="group"` + `aria-labelledby`。selected 态加 `aria-pressed` 或 `aria-current`。
- **动效**：hover transform `translateY(-1px)` + shadow 120 ms ease-out；prefers-reduced-motion 时只换 shadow。
- **Vue 实现**：基于 `n-card`（用 `:bordered`、`content-style`、`header`/`footer` 插槽）。包装件名 `BaseCard.vue`：
  - props：`variant: 'bordered'|'elevated'`、`interactive?: boolean`、`selected?: boolean`、`loading?: boolean`。
  - slots：`#icon`、`#header`、`#meta`、`default`、`#footer`。
  - `loading=true` 时把 default 换成 `BaseSkeleton`（cardPreset）。
  - 辅助：`@vueuse/core` 的 `useElementHover` 控制阴影类，避免 CSS 选择器对内嵌交互的污染。
- **联动**：emit `click`、`select`；不持有数据状态，selected 由父域决定（受控）。

---

## 2 · BaseBadge（009）

- **视觉**：9 tone × 3 size。`sm 18h` / `md 22h` / `lg 28h`，半径 6；可选 leading dot；neutral/brand/success/danger/info(citation)/concept/method/dataset/metric/author/venue。
- **状态**：`default` · `with-dot` · `hover`（仅 KG 类含交互时变深色），无 selected/disabled（纯展示）。
- **交互**：默认不可点；当承担过滤入口时升级为 `BaseChip` 而非 Badge。Badge 仅承担状态/类别信息。
- **A11y**：`role="status"`（针对动态变化，如 Stale）或纯视觉装饰时 `aria-hidden`，文案需有 sibling 标签可读。Citation `[12]` 必须 `aria-label="Citation 12"`。
- **动效**：无 enter/leave；只在配色切换时 `transition: background-color 120ms`。
- **Vue 实现**：自研 `BaseBadge.vue` 即可（`n-tag` 太重，含 closable/check 逻辑无法剪裁）。
  - props：`tone: BadgeTone`、`size: 'sm'|'md'|'lg'`、`dot?: boolean`、`leadingIcon?: Component`。
  - 用 UnoCSS shortcut：`badge-tone-{x}` 统一管理 tone token。
- **联动**：纯无状态展示，无 emit。

---

## 3 · BaseChip（010）

- **视觉**：28 h pill（radius 6 而非 999，区别于 status-pill），body-sm 13/15，trailing close icon 12。Hover `bg +1 step`；selected `brand-500` 1 px 描边 + bg `brand-50`。
- **状态**：`default` · `hover` · `selected` · `with-dot`(KG 类) · `with-close` · `close-hover`（关闭按钮变红区） · `empty`(+Add filter) · `loading`(skeleton 占位) · `error`(Failed to load + retry)。
- **交互**：
  - 整 chip 可点切换 selected；close icon 单独 hit-area，stopPropagation。
  - 键盘：`Space/Enter` 切换；`Backspace/Delete` 在 chip 上时移除（同 GitHub label）。
  - 多选 chip 组：左右箭头在 chip group 内 roving tabindex 移动焦点，仅活动项 `tabindex=0`。
- **A11y**：单选模式 `role="radio"` + `aria-checked`；多选 `role="checkbox"`；过滤入口 `role="button"`。close icon `aria-label="Remove {label}"`。
- **动效**：bg 120 ms；删除时 chip `scale(.96) → opacity 0`（120 ms），列表用 `@formkit/auto-animate` 自动 FLIP 收尾。
- **Vue 实现**：包装 `n-tag`（type/closable/checkable 三种用法），暴露 `BaseChip.vue` + `BaseChipGroup.vue`：
  - `BaseChipGroup` 用 Provide 派发 `selected`、`mode`、`roving focus`，子项注入即可。
  - `auto-animate` 装在 chip-group 容器上，零代码出列表动画。
- **联动**：v-model 双向，emit `remove`、`select`；Group 接管 keyboard。

---

## 4 · BaseTag (inline meta)（011）

- **视觉**：极克制的 inline 元数据行 —— 小写大字距、灰 500、bullet `•` 分隔（`EDGE ET AL. • 2024 • MICROSOFT RESEARCH • PREPRINT`）。本质是「分隔符化的小字段列表」而非可交互组件。
- **状态**：`default` · 不可点。承载文本溢出时支持中间省略（middle truncation）。
- **交互**：通常不可点；当某段是作者/年份过滤入口时，升级为 Chip 单独渲染。
- **A11y**：父元素加 `role="list"`，每段 `role="listitem"`；bullet 用 CSS `::before content` 注入并 `aria-hidden`。
- **动效**：无。
- **Vue 实现**：自研 `BaseTagInline.vue`，props `items: Array<string | {text, to?}>`。`to` 存在时段单独渲染为 `router-link` 并带 hover 下划线 —— 这是和 Chip 的边界：可跳转但不携带状态 → Tag；可切换状态 → Chip。
- **联动**：无状态。

---

## 5 · BaseModal（012）

- **视觉**：白底，radius 20，header（title + close）/ body（form 区）/ footer（次/主按钮右对齐）。背景 `rgba(15,15,20,.45)`。入场 `translateY(8px) + opacity 0 → 0` 200 ms ease-out。
- **状态**：`closed` · `opening` · `open` · `closing` · `loading-action`（confirm 按钮 spinner，整体仍可关）· `destructive`（confirm 按钮转 danger）。
- **交互**：
  - 打开：scroll lock（`@unhead/vue` 注入 `html { overflow:hidden; padding-right: var(--sbw) }` 避免抖动）。
  - 关闭：背景点击（可配置 `closeOnMaskClick`）、`Esc`、close 按钮、confirm 成功后。表单脏数据时拦截关闭 → 二次确认。
  - Focus：进入时焦点移到第一个可聚焦控件（非 close —— close 仅在没有控件时兜底）；`Tab/Shift-Tab` 循环（focus trap）；关闭后焦点归还触发元素。
- **A11y**：`role="dialog"` + `aria-modal="true"` + `aria-labelledby`（title id）+ `aria-describedby`（body 摘要 id）。destructive 用 `role="alertdialog"`。
- **动效**：opacity + translateY 200 ms；reduced-motion 时只切 opacity 80 ms。
- **Vue 实现**：底座选 `vue-final-modal v4`（比 `n-modal` 更适合做 Stack/嵌套，含原生 teleport + scroll lock + focus trap），上层暴露 `BaseModal.vue` + `useModal()` 命令式 API。
  - 为何不直接用 `n-modal`：业务需要多层 modal 栈（如 modal 中触发"添加来源"二级 modal）、命令式弹出（`showConfirm`、`showFormModal`），`vue-final-modal` 的 `useModal()` 原生支持。
  - 焦点陷阱用 `useFocusTrap`（@vueuse/integrations），onClickOutside 自动跳过 `popover/tooltip` 内嵌层（见专题 4）。
- **联动**：受控（v-model:show）+ 命令式（`useModal`）双形态；emit `confirm`、`cancel`、`after-leave`（用于清理临时表单 state）。

---

## 6 · BaseDrawer（013）

- **视觉**：右侧抽屉（也支持 left/top/bottom），宽度档：`md 480` / `lg 640` / `xl 880`（实体详情 + KG 预览）；左侧推开 8 px 主内容偏移仅在 `push` 模式启用。Header 含 title + tabs + close；body 滚动区；footer 行动条 sticky。
- **状态**：`closed` · `opening` · `open` · `pinned`（pin 后留下徽标继续操作主区，关闭其他 drawer 仅最小化此 drawer，见 EvidencePanel）· `loading` · `error`。
- **交互**：
  - 打开/关闭：与 Modal 同（Esc/mask/close），但 **overlay click 默认不关闭** —— Drawer 是「持续查看」语义，误点应安全。提供 `dismissible: boolean` 显式打开。
  - Pin：右上 pin 图标切换。pinned 状态下 mask 透明、不拦截 pointer，主区可继续操作（关键差异）。
  - Resize：`md/lg/xl` 段位切换或拖拽边缘（拖拽用 `@vueuse/core` `useDraggable` + 边界吸附）。
  - Focus：进入 trap；pinned 之后 trap 释放，但 Drawer 内仍保持自己的 tab order。
- **A11y**：`role="dialog"` + `aria-modal="false"`（注意：pinned 时确实是非模态）+ `aria-label` 描述抽屉用途。pin 切换 `aria-pressed`。
- **动效**：`translateX(100%) → 0` 200 ms cubic-bezier(.2,.8,.2,1)；pinned 时 mask `opacity 0` 120 ms。
- **Vue 实现**：底座 `n-drawer`（支持 placement、resizable、mask-closable），包装 `BaseDrawer.vue`：
  - 自定义 prop：`pinnable`、`pinned`、`widthPreset: 'md'|'lg'|'xl'`、`dismissible`。
  - pinned 行为通过 `:mask-closable="false"` + 自定义 `<Teleport>` 把 mask 替换成透明层。
  - 多 Drawer 共存：用 `provide BaseDrawerStackSymbol` 注入栈管理器，避免 z-index 互相打架。
- **联动**：v-model:show、emit `pin`、`resize`、`close`；与 EvidencePanel/EntityDetail 等 organism 通过 slot 注入内容。

---

## 7 · BaseTooltip（014 上）

- **视觉**：深色 `#1A1B22`，白字 12/16，箭头 6 px；hover 240 ms 后出现，离开 120 ms 消失。
- **状态**：`hidden` · `pending`（240 ms 内等待）· `visible` · `dismissed`（焦点离开/Esc）。
- **交互**：
  - 触发：mouseenter（240 ms 延迟）/ focus（即时）/ longpress（移动端 500 ms）。
  - 隐藏：mouseleave（120 ms） / blur / Esc / click 触发元素（认为已交互完成）。
  - 不可获取焦点 —— Tooltip 内不允许放可交互元素（要放就改 Popover）。
- **A11y**：`role="tooltip"`，触发元素 `aria-describedby="tip-id"`；移动端无 hover 时必须有等价 longpress 或语义已包含在 aria-label 中。
- **动效**：opacity + 2 px shift；reduced-motion 仅 opacity。
- **Vue 实现**：底座 `floating-vue` 的 `<Tooltip>`（基于 `@floating-ui/dom`，自动 flip/shift/边界避让，胜过 `n-tooltip` 的位置计算）。
  - 包装 `BaseTooltip.vue` 提供：`content`、`placement`、`delay`、`maxWidth` props。
  - 移动端检测（`useMediaQuery('(hover: none)')`）→ 自动改 longpress 触发。
- **联动**：无状态，单向展示。

---

## 8 · BasePopover（014 下）

- **视觉**：白底 radius 14，shadow 强于 card，内部允许富内容（标题 + 元数据栅格 + 链接行）。120 ms leave。
- **状态**：`closed` · `open` · `pinned`（click 触发版）· `loading`（异步加载详情）· `error`。
- **交互**：
  - 触发：`hover`（240 ms） · `click`（toggle） · `manual`（命令式）。RAG citation chip 用 hover 触发并允许移动到 popover 内（need bridge area，floating-ui safePolygon）。
  - 关闭：mouseleave（含 safePolygon 缓冲）/ outside click / Esc / 滚动滚出视口。
  - 与 Tooltip 区别：**Popover 内可获取焦点**，因此需要焦点管理：打开后第一个可聚焦元素接管焦点，Esc 回到触发。
- **A11y**：`role="dialog"` + `aria-modal="false"`，触发元素 `aria-expanded` + `aria-haspopup="dialog"`。
- **动效**：opacity + scale(.98 → 1) 120 ms。
- **Vue 实现**：底座 `floating-vue` 的 `<Dropdown>` 或 `<Menu>`（含 `safePolygon`），包装 `BasePopover.vue`：
  - 不用 `n-popover` 的原因：`floating-vue` 的 `safePolygon` 对 RAG citation 这种 hover-to-content 桥接是必需。
  - 异步内容：slot `#content` + props `loading`，与 `Suspense` 配合显示 SkeletonCard。
- **联动**：v-model:show、emit `open`、`close`、`resolve`（用户在 popover 内提交选择时）。

---

## 9 · BaseEmptyState（015）

- **视觉**：垂直居中，灰描线图标 (lucide `inbox`/`search-x`/`alert-triangle` 等) + 标题 (16/24 medium) + 说明 (14/22 muted) + 主 CTA + 次链接。说明文案必须 **包含可执行下一步**（"or press / to add sources"）。
- **状态**：本身就是 5 种语义场景：`no-data`(no documents yet) · `no-result`(no evidence found，承载 query 上下文) · `no-permission` · `no-path`(KG-specific) · `error`(降级 fallback 而非 ErrorState 时)。
- **交互**：CTA 必须立即可用（不需要再翻菜单）；说明里如有键盘提示（`/`、`g s`）必须真的能用 —— 由 `useMagicKeys` 全局注册。
- **A11y**：`role="status"`（非阻断）；图标 `aria-hidden`；CTA 是正常 button 语义。屏幕阅读器朗读顺序：状态文 → 主 CTA。
- **动效**：无入场动画（避免抢戏）；从 Skeleton 切到 Empty 时整块 fade 80 ms。
- **Vue 实现**：基于 `n-empty` 不够灵活（icon/CTA 都得 slot），直接自研 `BaseEmptyState.vue`：
  - props：`variant: EmptyVariant`（受限枚举，每个 variant 自带默认 icon/title/desc i18n key）、`actionLabel?`、`actionTo?`、`secondaryLabel?`。
  - slots：`#icon`、`#title`、`#description`、`#actions`（覆盖默认）。
  - 与 `useAsyncResource` 状态机直接对接（见专题 2）。
- **联动**：emit `action`、`secondary-action`。

---

## 10 · BaseSkeleton（016）

- **视觉**：浅灰矩形 `#ECECE8`，1.2 s `ease` shimmer（带渐变 mask）。Preset：`text-line`（h 12, radius 4）/ `avatar`（32 圆）/ `card`（320×180, radius 14）/ `kpi`（120×120）。
- **状态**：`shimmer`（默认）· `static`（reduced-motion 退化为静态灰块）。
- **交互**：不可聚焦、`aria-hidden`。
- **A11y**：父容器加 `aria-busy="true"` + `aria-live="polite"`（变化时朗读"加载完成"由数据态接管，不在 skeleton 自己上 announce）。
- **动效**：仅在 ≥ 800 ms 加载后展示（避免 flash —— 见专题 2 的 `useAsyncResource.minVisibleMs`）；shimmer 1.2 s 循环；reduced-motion 关闭。
- **Vue 实现**：底座 `n-skeleton`（提供 sharp/round/circle 三种基元），上层提供 `BaseSkeleton.vue`：
  - props：`preset: SkeletonPreset`、`lines?: number`、`block?: boolean`。
  - 复合 `BaseSkeletonCard.vue`、`BaseSkeletonList.vue` 直接拼好的占位，业务侧零拼装。
- **联动**：通常作为 `useAsyncResource` 的 idle/pending 渲染分支，不持有自己的状态。

---

## 11 · BaseToast（017）

- **视觉**：360 w，radius 16，左侧 4 px tone 强调条（success #16A34A / warning #F59E0B / danger #E5484D / info brand），右上 close。Shadow `0 12px 32px rgba(15,15,20,.12)`。从顶部右侧滑入 200 ms。
- **状态**：`success` · `warning` · `danger` · `info` · `empty`（无 toast 时 stack 空态）· `loading`（pending action，有 spinner）· `error`（toast 内部状态：retry）。
- **交互**：
  - 自动消失：success 4 s / info 5 s / warning 6 s / danger **不自动消失，用户必须确认**。
  - 悬停暂停计时（pause-on-hover）；focus 也暂停（pause-on-focus）。
  - swipe-right 或点 close 关闭；最多同时显示 3 条，超出排队；同 group key 的新 toast 替换旧（避免刷屏，比如"已保存"连点）。
  - 含 action（"Retry"、"Undo"）的 toast 时长翻倍（≥ 10 s）。
- **A11y**：
  - 普通 → `role="status"` + `aria-live="polite"`。
  - danger/含 action → `role="alert"` + `aria-live="assertive"`。
  - close 按钮 `aria-label="Dismiss notification"`。
- **动效**：translateX(16) + opacity 0 → 0 ease-out 200 ms；出场 translateX(16) + opacity 0 ease-in 120 ms；reduced-motion 仅 opacity。
- **Vue 实现**：自研 `useToast()` composable + `BaseToastViewport.vue`（单例 teleport 到 body）。
  - 不用 `n-message`：太死板，无法做 action button + retry。
  - 不用 `vue-toastification`：bundle 偏重，且与设计系统对齐成本高于自研。
  - 数据结构：`{ id, tone, title, description?, action?, durationMs, groupKey? }`，Pinia store `toastStore` 持有 queue。
- **联动**：命令式 API `toast.success(...)` / `toast.danger({ action })`；与 errorMapper 直连：API 4xx → inline；5xx + network → toast.danger。

---

## 12 · BaseAvatar（018）

- **视觉**：圆形，default 32（list）、24（inline meta）、40（user card）；hash → 1 of 9 KG tone bg；首字母 (1-2) `medium 600 not primary`；right-bottom 8 × 8 status dot；hover `1 px border subtle`。
- **状态**：`initials`（默认）· `image`（有 avatar URL，img 加载失败回退 initials）· `with-status`（online/busy/danger）· `hover` · `loading`(image 加载中显示 skeleton 圆) · `group`（叠加显示，最多 3 个 + `+N`）。
- **交互**：默认不可点；置于 user card 时整 card 可点；group 展开点击触发 popover 列表。
- **A11y**：`role="img"` + `aria-label="{full name}"`（首字母对屏幕阅读器无意义，必须有完整名）；status dot `aria-label="Online"` 等。
- **动效**：image fade-in 120 ms；group hover 时叠加错位 4 px 展开。
- **Vue 实现**：自研 `BaseAvatar.vue` + `BaseAvatarGroup.vue`：
  - 不用 `n-avatar`：hash → tone 映射、KG 9 tone 调色板需要项目特定逻辑。
  - 工具函数 `hashToTone(name: string): KgTone` 放 `utils/color.ts`，确保同名同色。
  - image 加载失败：用 `img.onerror` 切到 initials 分支，纯 CSS 不行。
- **联动**：emit `click`（仅 interactive 模式）；Group 用 slot 接受 `BaseAvatar` 子项，自动叠加。

---

## 13 · BaseTabs（019）

- **视觉**：水平 tab list，活动项下方 2 px brand 下划线，文案 medium；非活动 muted。键盘提示行紧贴下方（`← → Arrow keys cycle / Home End Jump to ends`）—— 提示该实现为 a11y 标准。
- **状态**：`default` · `hover` · `active` · `focused`(键盘) · `disabled` · `with-badge`（tab label 后跟计数 badge）· `overflow`(超出宽度时尾部 "more ▾" 折叠) · `loading`(panel 内容)。
- **交互**：
  - 鼠标：点击切换。
  - 键盘：`←/→` 在 tablist 内移动焦点（**自动激活模式 vs 手动激活模式**：默认 manual —— 移动只移焦点，`Enter/Space` 激活；自动模式仅在 tab 切换无副作用时启用，如纯展示页签）。`Home/End` 跳首尾。
  - 移动端：横向滚动，活动 tab 自动 scrollIntoView centered。
- **A11y**：`role="tablist"` + 每个 tab `role="tab"` + `aria-selected` + `aria-controls`；panel `role="tabpanel"` + `aria-labelledby`。**唯一活动 tab `tabindex=0`，其余 `tabindex=-1`**（roving tabindex）。
- **动效**：下划线用单独 `::after` + `transform: translateX()` + `width` 联动，120 ms ease-out（避免 layout 抖）。
- **Vue 实现**：底座 `n-tabs`（已内置 a11y），但要重做下划线样式 + roving tabindex 包装为 `BaseTabs.vue`：
  - props：`activationMode: 'auto'|'manual'`（默认 manual）、`size`、`align`。
  - slots：每个 panel 用 `BaseTabPane.vue` 包装。
  - Provide `BaseTabsSymbol`：`{ activeKey, register, unregister, focusKey }` 给子 pane / 子 tab，避免 prop 透传。
- **联动**：v-model:value；emit `update:value`、`tab-click`。

---

## 14 · BaseDivider（020）

- **视觉**：3 种：`default`（full-width 1 px `#E4E4E0`）/ `inset`（两端淡出渐变，inline-card 内用）/ `vertical`（h 24, 居中 inline）。
- **状态**：纯展示，无态。
- **交互**：无。
- **A11y**：`role="separator"`；vertical 加 `aria-orientation="vertical"`。装饰性场景可 `aria-hidden`。
- **动效**：无。
- **Vue 实现**：自研 1 行 `BaseDivider.vue`（`n-divider` 体积过大且含 title 槽位）：
  - props：`variant: 'default'|'inset'|'vertical'`、`spacing?: number`（4 的倍数）。
- **联动**：无。

---

## 15 · BaseProgress（021）

- **视觉**：4 种：
  - Linear（h 8 / 12）：determinate / indeterminate（marquee）/ With Stages（多段彩条）。
  - Ring（48 / 56 / 80）：determinate / indeterminate（旋转）。
  - Tiny mini progress（行内 4 h，无 label，多用于 list row）。
  - Caption patterns：`Short Value` / `Long Form`（双行说明 + 进度行）。
- **状态**：`determinate` · `indeterminate` · `success`(完成 100 %) · `warning`(慢/降级) · `danger`(失败暂停) · `paused`。
- **交互**：通常不可交互；点击可触发"取消"或"查看任务"时升级为按钮组合，不在 BaseProgress 内承担。
- **A11y**：
  - determinate → `role="progressbar"` + `aria-valuenow` + `aria-valuemin=0` + `aria-valuemax=100` + `aria-label="Ingesting PDFs"`。
  - indeterminate → 同上但不带 `aria-valuenow`。
  - 长跑任务 → 外层 `aria-live="polite"` 朗读 milestone（"50% complete"），频率 ≥ 10 s 一次，避免刷屏。
- **动效**：determinate 进度变化 `width` 200 ms ease-out；indeterminate 1.4 s loop；reduced-motion → 静态 50% bar + percentage 文本（不旋转）。
- **Vue 实现**：底座 `n-progress`（line/circle）+ 自研 stage bar：
  - 包装 `BaseProgressBar.vue` / `BaseProgressRing.vue` / `BaseProgressStages.vue`。
  - props：`value?: number`、`status: ProgressStatus`、`indeterminate?: boolean`、`caption?: { short?: string; long?: { milestones: string[] } }`。
- **联动**：受控；emit `complete`（value 抵达 100 时一次性触发，业务侧可联动 toast.success）。

---

## 16 · BaseStatusPill（022）

- **视觉**：与 Chip 类似但 **radius 999**（完整 pill）+ leading dot 6 px；专用于"状态名词"如 `Healthy / Indexing / Parsing / Ready / Stale community / Failed / Running`。色阶比 Badge 更柔（bg-50, text-700）。
- **状态**：枚举：`healthy` · `indexing` · `parsing` · `ready` · `stale` · `failed` · `running`。每个 status 自带 dot color + label i18n key + 是否带 spinner（`indexing/parsing/running` 带）。
- **交互**：通常不可点；click 可打开 BasePopover 显示状态历史（如最后一次成功时间、错误堆栈摘要）。
- **A11y**：`role="status"` + `aria-live="polite"`（状态变化时朗读）。spinner `aria-hidden`，文本本身已表达进行中。
- **动效**：状态切换时 bg 颜色 120 ms 过渡；带 spinner 的 status 用 1.2 s 圆点呼吸（reduced-motion 关闭）。
- **Vue 实现**：自研 `BaseStatusPill.vue`：
  - props：`status: StatusKind`、`label?: string`（覆盖默认 i18n）、`detail?: string`（hover popover 内容）。
  - 内部维护 `STATUS_META` 表：`{ tone, hasSpinner, defaultI18nKey }`，单一来源。
- **联动**：emit `click`（可选），与 BasePopover 组合时受控显隐。

---

## 17 · BaseIconButton（023）

- **视觉**：32×32 方形，radius 10，默认透明 bg；hover `bg #F4F4F0`；active `bg #E4E4E0 + scale(.96)`；disabled `opacity 40`。lucide line icons 16 px。
- **状态**：`default` · `hover` · `active(pressed)` · `focused` · `disabled` · `loading`（icon 换成 spinner）· `toggle-on/off`（侧栏 expand、language switcher 等）。
- **交互**：纯按钮语义；toggle 模式按 `Space/Enter` 切换；hold 模式（如音量长按）用 `pointerdown/up`。
- **A11y**：**必须有 `aria-label`**（没有可见文本！）；toggle 用 `aria-pressed`；菜单触发用 `aria-haspopup` + `aria-expanded`。所有 IconButton 强制 Tooltip 配套展示完整 label —— 用 UnoCSS preset 强制要求或 ESLint 自定义规则在 PR 阶段拦截。
- **动效**：scale + bg 120 ms；reduced-motion 关 scale。
- **Vue 实现**：自研 `BaseIconButton.vue`（包装 `n-button :text :circle` 在样式上拉不齐）：
  - props：`icon: Component`、`size: 24|32|40`、`tone?: 'neutral'|'brand'|'danger'`、`tooltip?: string`、`pressed?: boolean`、`loading?: boolean`。
  - 自动套 `BaseTooltip` 当 `tooltip` 存在；toggle 时按 `pressed` 切 `aria-pressed`。
  - dev-only 断言：未传 `aria-label` 也未传 `tooltip` 时 `console.warn`。
- **联动**：emit `click`、`update:pressed`（toggle 模式）。

---

# 专题展开

## 专题 1 · Modal vs Drawer vs Popover 决策树

> 这是本项目最容易做错、又最影响 RAG 体验的判断。

### 1.1 判定表

| 场景 | 时长 | 与主上下文关系 | 输出 |
|---|---|---|---|
| 确认删除文档 | < 5 s | 阻断 | **Modal** (alertdialog) |
| 编辑短表单（重命名、添加标签） | 10–30 s | 阻断 | **Modal** |
| 创建新会话（含模板选择） | 30–60 s | 阻断 | **Modal** |
| 查看证据片段（消息中的 citation） | 持续，需对照阅读 | **并存** | **Drawer (pinnable)** |
| 查看实体详情（KG 节点） | 持续，可能在图上跳来跳去 | **并存** | **Drawer** |
| 文献入库进度详情 | 持续后台 | 并存 | **Drawer** 或 inline panel |
| 引用 chip 悬浮预览（前 3 行 + 评分） | < 5 s 浏览 | 非阻断 | **Popover (hover, safePolygon)** |
| 用户头像点击的快捷菜单 | < 5 s | 非阻断 | **Popover (click)** |
| 字段帮助说明 | 阅读 1-2 s | 非阻断 | **Tooltip**（不要 Popover） |
| 错误堆栈追溯 | 中等，可能要复制粘贴 | 并存 | **Drawer** 或 **Popover (pinned)** |

### 1.2 三句话决策树

1. **要不要阻断主流程？** 要 → Modal；不要 → 进 2。
2. **要不要持续可见 + 主区可继续操作？** 要 → Drawer (pinnable)；不要 → 进 3。
3. **内容里有没有可聚焦的交互元素？** 有 → Popover（focus 进入）；没有 → Tooltip。

### 1.3 反模式

- 用 Modal 装 KG 子图（用户必须在图上反复跳）→ 应该是 Drawer。
- 用 Drawer 做删除确认（阻断动作放抽屉是反直觉）→ 应该 Modal。
- 用 Tooltip 装"打开详情"链接（Tooltip 不允许可聚焦内容）→ 应该 Popover。

---

## 专题 2 · Skeleton → Data/Empty/Error 状态机

### 2.1 统一的 `useAsyncResource`

```ts
// composables/useAsyncResource.ts
type Phase = 'idle' | 'pending' | 'success' | 'empty' | 'error'

interface UseAsyncResourceOptions<T> {
  minVisibleMs?: number   // pending 至少展示多久，避免 flash，默认 300
  skeletonAfterMs?: number // pending 多久才开始展示 skeleton，默认 200
  emptyIf?: (data: T) => boolean // 把 success 进一步分流到 empty
}

interface UseAsyncResourceReturn<T> {
  phase: Ref<Phase>
  data: Ref<T | null>
  error: Ref<Error | null>
  refresh: () => Promise<void>
  showSkeleton: ComputedRef<boolean> // 真正展示骨架的窗口
}
```

### 2.2 状态机图

```
                ┌──── (start) ──────┐
                ▼                   │
              idle ── refresh() ─► pending
                                    │
                  ┌─────────────────┤
                  │                 │
                  ▼                 ▼
              error             success
                  │                 │
                  │                 ▼ emptyIf?
                  │           ┌─────┴─────┐
                  │           ▼           ▼
                  │         empty       data
                  └──────────┴───────────┘
                          (refresh)
```

### 2.3 渲染分流模板

```vue
<template>
  <BaseSkeletonList v-if="r.showSkeleton.value" :rows="6" />
  <BaseErrorState v-else-if="r.phase.value === 'error'" :error="r.error.value" @retry="r.refresh" />
  <BaseEmptyState v-else-if="r.phase.value === 'empty'" variant="no-result" @action="r.refresh" />
  <!-- 真正的数据视图 -->
  <DocumentList v-else :items="r.data.value!" />
</template>
```

### 2.4 防 flash 规则

- `pending` < 200 ms → 直接保留旧内容（不闪 skeleton）。
- 200 ≤ pending < 800 ms → 显示 skeleton 至少到 800 ms（min visible），避免一闪而过。
- pending > 5 s → 在 skeleton 上叠加 "Still loading…" caption + cancel button（取消请求）。

---

## 专题 3 · Toast vs Banner vs Inline Error

| 维度 | Inline Error | Toast | Banner |
|---|---|---|---|
| **严重度** | low – mid（可恢复，单字段） | mid – high（全局事件，可消失） | high（全局阻断/降级，持续） |
| **可恢复性** | 用户立即修复 | 多数无需操作，少数提供 Undo/Retry | 通常需联系管理员或等待系统恢复 |
| **位置** | 紧贴出错字段下方 | 顶部右侧角，最多 3 叠 | 页面顶部，sticky |
| **持久性** | 直到字段变更 | 4-6 s 自动消失（danger 例外） | 直到状态恢复或用户手动关闭 |
| **a11y** | `aria-describedby` + `aria-invalid` | `role="status"` 或 `alert` | `role="region"` + `aria-label` |
| **典型用例** | 表单校验 / API 400 字段错 | 保存成功 / 上传完成 / 网络瞬断 | 知识库正在重建索引 / 后端降级 / 维护窗口 |
| **不能用于** | 全局事件 | 阻断性错误（用户没看到就消失） | 单字段错误（位置太远） |

### 3.1 错误映射规则（与 errorMapper 联动）

```
API 4xx + 含 fieldErrors → Inline (per field) + 表单顶部 BaseBanner summary
API 4xx 无字段映射     → Toast.warning + 描述
API 5xx / Network      → Toast.danger（持久）+ Retry action
Auth 401               → Modal.alertdialog（强制重新登录）
全局降级（FF 关闭）    → Banner（页面顶部 sticky）
```

### 3.2 一句话原则

> 用户必须看到 → Banner / Modal；用户应该看到 → Toast；用户已经在看 → Inline。

---

## 专题 4 · Focus trap 与 z-index 层叠

### 4.1 层叠段位（已在全局公约重申）

```
toast    4000   <- 永远在最上层，但不抢焦点（aria-live）
tooltip  3200   <- 只展示，不参与 trap
popover  3100
modal    3000   <- 默认主 trap 层
drawer   2000
dropdown 1000
sticky    100
base        0
```

### 4.2 多层焦点陷阱栈

实现要点：

- 全局 Pinia store `focusTrapStack: TrapHandle[]`。
- 任意 `BaseModal / BaseDrawer / BasePopover(modal)` 打开时 `pushTrap()`，关闭时 `popTrap()`。
- **只有栈顶 trap 处于激活状态**；下层 trap pause（不释放焦点引用）。
- Esc 优先关闭栈顶（Tooltip → Popover → Modal → Drawer 反向出栈）。

### 4.3 嵌套规则

| 嵌套场景 | 焦点行为 |
|---|---|
| Modal 内开 Tooltip | Tooltip 不抢 focus；Esc 只关 Tooltip |
| Modal 内开 Popover | Popover 是新 trap，Modal trap 暂停；Popover 关闭后 trap 还给 Modal |
| Modal 内开二级 Modal | 第二层 trap 入栈；二级关闭后第一层 trap 恢复 |
| Drawer pinned + 主区操作 | Drawer trap **释放**（pinned 是非模态）；Drawer 内仍维持自己的 tab order |
| Drawer 内开 Modal | Modal trap 入栈，Drawer trap 暂停 |
| Popover 内开 Tooltip | Tooltip 走 hover；不影响 Popover trap |

### 4.4 onClickOutside 必须跳过

`useFocusTrap` + `onClickOutside` 都要把"上层 floating 元素"列入 `ignore`，否则在 Modal 里点 Popover 会立刻关 Modal。统一封装：

```ts
useClickOutside(modalRef, onClose, {
  ignore: [() => document.querySelectorAll('[data-floating-layer]')]
})
```

所有 floating-vue / vue-final-modal 的根元素强制带 `data-floating-layer`，由公共 mixin 注入。

---

# 小结

## 最值得固化的 3 条规范

1. **状态机统一封装在 `useAsyncResource`**：Skeleton / Empty / Error / Data 不再各写各的，避免业务侧出现"加载完一闪、空态没显示"等典型 bug；并强制 `minVisibleMs` 防 flash 与 `skeletonAfterMs` 防 jank。
2. **Modal / Drawer / Popover 三选一走判定表**：用「阻断 vs 持续 vs 浏览」+「内部是否有可聚焦元素」两个轴定位，禁止用 Tooltip 装可点链接、用 Modal 装持续查看面板这两个反模式。
3. **Focus trap 走全局栈，Esc 反向出栈**：所有 floating 容器统一 `pushTrap/popTrap`，加 `data-floating-layer` 标记给 `onClickOutside` 兜底，规避层叠误关闭与焦点丢失。

## 1 个最容易踩坑的盲区

> **Drawer pinned 之后是「非模态」，不要复用 Modal 的焦点陷阱模型。**

很多团队会把 Drawer 当作"侧边 Modal"实现，pinned 时仍然 trap focus，结果用户既无法操作主区（pin 等于没生效），又被 `tabindex=-1` 锁在抽屉里。
正确实现：`pinned=true` 时立即 `popTrap()`、设置 `aria-modal="false"`、mask 不拦截 pointer-events、保持自身内部 tab order 即可。这一行为差异必须在 `BaseDrawer.vue` 的单元测试里以"切换 pin 状态后焦点是否能跳出抽屉"作为断言保护。

---

# UI 参数注入（来自 UI_PROMPTS §02-G ~ §02-W）

> 说明：以下表格把 `UI_PROMPTS.md` 第 867–2413 行 17 个组件 task 段里的精确数值抽取出来，作为前端工程师可直接落地的数字。
> 与本文档前段交互描述并存：上文给"语义/状态/a11y/动效"，本段给"尺寸/颜色/字体/动效阈值"。
> 数值不带 `px`；颜色用 `token #HEX` 双写。`—` 表示 PROMPTS 未指定。冲突项以 `FRONTEND_DESIGN_SPEC.md` 为准并注明。

## 1 · BaseCard

#### UI 参数（来自 UI_PROMPTS §02-G）
| 类别 | 值 |
|---|---|
| 宽度 / 高度 | 320 × 180（spec 样张） |
| padding | 20（统一 inner） |
| 字体 | header h3 Inter SemiBold 20/24.2 600；meta caption Inter Regular 12/14.5；body Inter Regular 14/16.9；footer ghost button body |
| 颜色 | bg `bg-surface #FFFFFF`；border `border-subtle #E4E4E0`；meta `text-tertiary #8C8C82`；divider `border-subtle #E4E4E0` |
| 圆角 | 14 |
| 阴影 | bordered 无阴影；elevated default `shadow-sm 0 1 2 rgba(15,15,20,.04)`，hover `shadow-md 0 4 12 rgba(15,15,20,.06)` |
| 边框 | bordered 1 px `border-subtle #E4E4E0`；elevated 无 |
| 动效 | hover 120 ms ease-out（阴影 + translateY(-1)，reduced-motion 仅切阴影） |
| 焦点环 | `0 0 0 3 rgba(79,70,229,.20)` |
| 内部结构 | header / meta / divider 1 px / body 3 行 / footer ghost button "Open ↗" |

## 2 · BaseBadge

#### UI 参数（来自 UI_PROMPTS §02-H）
| 类别 | 值 |
|---|---|
| 高度 | sm 18 / md 22 / lg 28 |
| padding | —（PROMPTS 未写，建议 0/6 sm，0/8 md，0/10 lg） |
| 字体 | sm JetBrains Mono 10/12.1；md Inter Medium 11/13.3（meta）；lg Inter Regular 13/15.7（body-sm） |
| 颜色 (tone → bg / text) | neutral `bg-subtle #F4F4F1` / `text-secondary #515151`；brand `brand-50 #EDF0FF` / `brand-700 #2A1FAF`；success `#EBFCF5` / `#047856`；warning `#FFFAEB` / `#B45208`；danger `#FDF1F1` / `#B91B1B`；info `#EBFDFF` / `#0E7490`；KG concept `#4F46E4 mix-50` / `#4F46E4`；method `#10B881 mix-50` / `#10B881`；dataset `#F59E0A mix-50` / `#F59E0A`；metric `#06B6D3 mix-50` / `#06B6D3`；author `#A854F7 mix-50` / `#A854F7`；venue `#EB4799 mix-50` / `#EB4799` |
| 圆角 | 6 |
| 边框 / 阴影 | 无 |
| 前导点 | 6 × 6 round，与 text 同色 |
| 动效 | 仅 `background-color 120 ms` 切色，无 enter/leave |
| Citation 例外 | citation 必须 info-500 `#06B6D3`，禁用 brand indigo |

## 3 · BaseChip

#### UI 参数（来自 UI_PROMPTS §02-I）
| 类别 | 值 |
|---|---|
| 高度 | 28 |
| padding | —（建议 0/10 含 dot 时 0/8） |
| 字体 | Inter Regular body-sm 13/15.7 |
| 颜色 | default bg `bg-subtle #F4F4F1`，text `text-secondary #515151`；brand bg `brand-50 #EDF0FF` text `brand-700 #2A1FAF`；KG tone 同 Badge；hover bg「+1 step」（subtle → muted #EAEAE5） |
| Selected 态 | 1 px border `brand-500 #4F46E4` + bg `brand-50 #EDF0FF` |
| 圆角 | 6（**与 status-pill 999 区分**） |
| 前导 dot | 12 × 12 round |
| 关闭图标 | Lucide "×" 12 stroke 1.5；hover text → `text-primary #1A1A1A` |
| 动效 | bg 120 ms；删除 `scale(.96) → opacity 0` 120 ms，列表 FLIP 用 auto-animate |
| 焦点 | roving tabindex；focus ring 通用 `0 0 0 3 rgba(79,70,229,.20)` |

## 4 · BaseTag (inline meta)

#### UI 参数（来自 UI_PROMPTS §02-J）
| 类别 | 值 |
|---|---|
| 高度 | 20 |
| padding | 0 / 6 |
| 字体 | Inter Medium meta 11/13.3 500；可选 uppercase |
| 颜色 | text `text-tertiary #8C8C82`；无 bg / 无 border |
| 圆角 | —（无 bg 故不可见） |
| 分隔符 | 中点 `·`（U+00B7），由 CSS `::before` 注入 |
| 动效 | 无 |
| 链接态 | 含 `to` 时 hover 下划线（router-link） |

## 5 · BaseModal

#### UI 参数（来自 UI_PROMPTS §02-K）
| 类别 | 值 |
|---|---|
| 宽度 / 高度 | 600 × 640（参考样张）；居中 viewport |
| padding | 32（容器 inner） |
| 字体 | title Inter Bold h2 22/26.6 700 `text-primary #1A1A1A`；body Inter Regular 14/16.9；close icon Lucide 20 `text-tertiary #8C8C82` |
| 圆角 | 20（radius-xl） |
| 阴影 | `shadow-lg 0 12 32 rgba(15,15,20,.10)` |
| 背景 | `bg-surface #FFFFFF` |
| 蒙层 | `rgba(15,15,20,.40)` 全 viewport > 冲突：PROMPTS=.40 / SPEC 前段=.45 → 采用 SPEC `.45` |
| 行高 | header 56 / footer 56；body 字段间距 24 |
| 焦点环 | Primary 按钮 `0 0 0 3 rgba(79,70,229,.20)` brand-500 |
| 动效 | enter 200 ms ease-out（opacity + translateY 8）；exit 同曲线 |
| 关闭键 | Esc / mask click（可配 `closeOnMaskClick`） / close 按钮 |
| Footer | 右对齐：Secondary "Cancel" + Primary，按钮间距 12 |

## 6 · BaseDrawer

#### UI 参数（来自 UI_PROMPTS §02-L）
| 类别 | 值 |
|---|---|
| 宽度档 | small 360 / medium 440 / large 800 > 冲突：PROMPTS=360/440/800 / SPEC 前段=md 480 / lg 640 / xl 880 → 采用 SPEC（480/640/880） |
| 高度 | 100 vh |
| padding | 24（inner） |
| 字体 | title Inter SemiBold h3 20/24.2 600；close `×` Lucide 20 |
| 颜色 | bg `bg-surface #FFFFFF`；附着侧 1 px left `border-subtle #E4E4E0` |
| 圆角 | 附着侧 0；远端可选 inset 14 |
| 阴影 | `shadow-lg 0 12 32 rgba(15,15,20,.10)` |
| 行高 | header 64；sticky footer 64（有 action 时） |
| 蒙层 | 与 Modal 同 `rgba(15,15,20,.45)`（SPEC）；pinned 时 `opacity 0` 120 ms 透明且不拦截 pointer |
| 动效 | `translateX(100%) → 0` 200 ms cubic-bezier(.2,.8,.2,1) |
| 关闭键 | Esc / close；mask click **默认不关闭**（持续语义） |
| a11y | `aria-modal=true`（默认） / `false`（pinned）；focus trap |

## 7 · BaseTooltip

#### UI 参数（来自 UI_PROMPTS §02-M）
| 类别 | 值 |
|---|---|
| 偏移 | 触发元素上方 8 |
| 最大宽 | 240 |
| padding | 8 / 10 |
| 字体 | Inter Regular body-sm 13；text `#FFFFFF` |
| 颜色 | bg `#1A1A1A`（text-primary 反色，非 SPEC dark `#1A1B22`） > 冲突：PROMPTS=#1A1A1A / SPEC 前段=#1A1B22 → 采用 SPEC `#1A1B22` |
| 圆角 | 8 |
| 箭头 | 6 × 6 chevron |
| 阴影 | —（建议 `shadow-md`） |
| 动效 | enter 240 ms 延迟后出现，opacity + 2 px shift；exit 120 ms |
| 触发 | hover 240 ms / focus 即时 / 移动端 longpress 500 ms |
| a11y | `role="tooltip"`；不可获取焦点 |

## 8 · BasePopover

#### UI 参数（来自 UI_PROMPTS §02-N）
| 类别 | 值 |
|---|---|
| 最大宽 | 320 |
| padding | 16 |
| 字体 | title Inter SemiBold body 14 600；body-sm `text-secondary #515151` |
| 颜色 | bg `bg-surface #FFFFFF`；border 1 px `border-subtle #E4E4E0` |
| 圆角 | 14 |
| 阴影 | `shadow-md 0 4 12 rgba(15,15,20,.06)` |
| 动效 | enter opacity + scale(.98 → 1) 120 ms；exit 120 ms |
| 触发 | hover 240 ms（safePolygon） / click / manual |
| 关闭 | mouseleave + safePolygon / outside click / Esc / 滚出视口 |
| a11y | `role="dialog"` `aria-modal="false"`；可获取焦点 |

## 9 · BaseEmptyState

#### UI 参数（来自 UI_PROMPTS §02-O）
| 类别 | 值 |
|---|---|
| 图标容器 | 40 × 40 round，bg `bg-subtle #F4F4F1` |
| 图标 | Lucide line（inbox / search-x / alert-triangle），size 20，stroke 1.5，color `text-tertiary #8C8C82` |
| 字体 | title Inter SemiBold h4 18/21.8 600 `text-primary #1A1A1A`；description Inter Regular body 14/22 `text-secondary #515151` > 冲突：PROMPTS body 14/22 / SPEC scale body=14/16.9 → 文案行高采用 PROMPTS 22 |
| 最大宽 | description 360 居中 |
| padding / 间距 | title margin-top 16；description margin-top 4 |
| 颜色 | 同上 |
| 动效 | 无 enter；Skeleton → Empty 切换时整块 fade 80 ms |
| CTA | 主按钮在 description 下方（按 BaseButton md 40h） |
| a11y | `role="status"`；icon `aria-hidden` |

## 10 · BaseSkeleton

#### UI 参数（来自 UI_PROMPTS §02-P）
| 类别 | 值 |
|---|---|
| Preset | text-line h 12 radius 6；avatar 32 circle；card 320 × 180 radius 14；KPI 336 × 128 radius 14 |
| 颜色 | gradient `bg-muted #EAEAE5 → bg-subtle #F4F4F1` > 冲突：PROMPTS gradient / SPEC 前段定为 `#ECECE8` → 采用 PROMPTS 双色渐变 |
| shimmer 周期 | 1.2 s ease 循环 |
| 触发阈值 | 仅在 ≥ 800 ms pending 后才出现（防 flash） |
| 最小可见 | 300 ms（防 jank，见 useAsyncResource.minVisibleMs） |
| 动效 | reduced-motion 降级为静态灰块 |
| a11y | 自身 `aria-hidden`；父容器 `aria-busy="true"` + `aria-live="polite"` |
| 复合示例 | LibraryCard skeleton：title 60 % 宽、desc 2 行 90 % / 70 %、4 个 50 w 小 chip |

## 11 · BaseToast

#### UI 参数（来自 UI_PROMPTS §02-Q）
| 类别 | 值 |
|---|---|
| 宽度 | 360 |
| padding | 12 / 16 |
| 字体 | title Inter SemiBold body-sm 13 600；description Inter Regular body-sm 13 `text-secondary #515151` |
| 颜色 | bg `bg-surface #FFFFFF`；border 1 px `border-subtle #E4E4E0` |
| 圆角 | 14 > 冲突：PROMPTS=14 / SPEC 前段=16 → 采用 SPEC `16` |
| 阴影 | `shadow-lg 0 12 32 rgba(15,15,20,.10)` > 冲突：SPEC 前段 `0 12 32 rgba(15,15,20,.12)` → 采用 SPEC `.12` |
| 左侧色条 | 4 wide；success `success-500 #10B881` / warning `warning-500 #F59E0A` / danger `danger-500 #EE4444` / info `brand-500 #4F46E4` > 冲突：SPEC 前段 danger=`#E5484D`、info=brand → 采用 SPEC danger=`#E5484D` |
| 状态图标 | left 20 size；close right |
| 锚点 | viewport top-right，边距 24，stack 间距 12，最多 3 条 |
| 自动消失 | success 4 s / info 5 s / warning 6 s / **danger 不自动消失**；含 action 翻倍 ≥ 10 s |
| 暂停 | hover / focus 暂停计时 |
| 动效 | enter `translateX(16) + opacity 0 → 0` 200 ms ease-out；exit 120 ms ease-in |
| a11y | 普通 `role="status" aria-live="polite"`；danger / action `role="alert" aria-live="assertive"` |

## 12 · BaseAvatar

#### UI 参数（来自 UI_PROMPTS §02-R）
| 类别 | 值 |
|---|---|
| 直径 | sm 24 / default 32 / lg 40 |
| 字体 | initials Inter SemiBold 600 `text-primary #1A1A1A`（1-2 个字母） |
| 颜色 | bg = hash → KG 9 tone 的 `-50` muted（brand / violet `#A854F7` / pink `#EB4799` / cyan `#06B6D3` 等） |
| 圆角 | 999（完整圆） |
| 状态点 | 8 × 8 round，bottom-right；success `#10B881` / danger `#EE4444` |
| 边框 | hover 1 px `border-subtle #E4E4E0` |
| 动效 | image fade-in 120 ms；group hover 错位 4 px 展开 |
| Group | 最多叠加 3 + `+N`；展开点击触发 popover |
| a11y | `role="img"` + `aria-label="{full name}"`；status dot `aria-label` |

## 13 · BaseTabs

#### UI 参数（来自 UI_PROMPTS §02-S）
| 类别 | 值 |
|---|---|
| Tab 高度 | 40 |
| padding | 0 / 16 |
| 字体 | Inter SemiBold body-sm 13 600 |
| 颜色 | active text `text-primary #1A1A1A`；inactive `text-tertiary #8C8C82`，hover → `text-secondary #515151` |
| 下边框 | 1 px `border-subtle #E4E4E0`（tablist 底） |
| 下划线 | active 2 px `brand-500 #4F46E4`；用 `::after` + `transform/width` 联动 |
| 圆角 | 0（pill 容器无圆角，下划线方形端） |
| 动效 | 120 ms ease-out 下划线 X 平移 + 宽度变化 |
| 键盘 | `←/→` cycle，`Home/End` 跳首尾；roving tabindex（active=0，其余=-1） |
| a11y | `role="tablist" / tab / tabpanel` + `aria-selected` + `aria-controls` |

## 14 · BaseDivider

#### UI 参数（来自 UI_PROMPTS §02-T）
| 类别 | 值 |
|---|---|
| 默认 | 1 px 横向 full-width，色 `border-subtle #E4E4E0` |
| inset 变体 | 1 px gradient，两端 fade 到透明，用于卡片内 |
| vertical 变体 | 1 px 宽，高 24，inline 居中 |
| 圆角 / 阴影 / 动效 | 无 |
| a11y | `role="separator"`；vertical 加 `aria-orientation="vertical"`；装饰性场景 `aria-hidden` |

## 15 · BaseProgress

#### UI 参数（来自 UI_PROMPTS §02-U）
| 类别 | 值 |
|---|---|
| Linear | track 100 % 宽 × 4 h，radius 999（pill）；bg `bg-muted #EAEAE5`；fill `brand-500 #4F46E4` > 冲突：PROMPTS h=4 / SPEC 前段 h=8 或 12 → 行内 4，块级 8/12，皆采用 SPEC |
| Indeterminate Linear | 30 % 宽段，左→右 1.4 s ease-in-out infinite |
| Ring | 直径 16 / 20 / 24；stroke 2；arc `brand-500`；track `bg-muted` > 冲突：PROMPTS 16/20/24 / SPEC 前段 48/56/80 → 采用 SPEC（48/56/80 为面板用，16/20/24 为 inline 用，互补不冲突） |
| Indeterminate Ring | 旋转 1 s linear |
| Tiny inline | 88 × 3，radius 999，fill `brand-500`（document row 内嵌） |
| 状态色 | success `#10B881` / warning `#F59E0A` / danger `#EE4444` / paused `text-tertiary` |
| Caption | "70%" 或 "step 4 of 7 · 04:18 elapsed · ~03:30 left" |
| 动效 | determinate width 200 ms ease-out；reduced-motion 静态 + percentage 文本 |
| a11y | `role="progressbar"` + `aria-valuenow/min=0/max=100` + `aria-label` |

## 16 · BaseStatusPill

#### UI 参数（来自 UI_PROMPTS §02-V）
| 类别 | 值 |
|---|---|
| 高度 | 22 |
| padding | 0 / 8 |
| 字体 | JetBrains Mono mono-sm 11/13.3 600 |
| 圆角 | 999（pill，**与 Chip 6 区分**） |
| 前导 glyph | `●/◐/⚠/⊘` + label |
| 变体 (bg / text / dot) | Healthy `success-50 #EBFCF5` / `success-700 #047856` / dot `#10B881`；Indexing `brand-50 #EDF0FF` / `brand-700 #2A1FAF` / `#4F46E4`；Parsing 同 Indexing；Ready 同 Healthy；Stale community `warning-50 #FFFAEB` / `warning-700 #B45208` / `#F59E0A`；Failed `danger-50 #FDF1F1` / `danger-700 #B91B1B` / `#EE4444`；Running `info-50 #EBFDFF` / `info-700 #0E7490` / `#06B6D3`（pulsing） |
| 间距 | 行内 pill 间距 12 |
| 动效 | bg 切换 120 ms；indexing/parsing/running dot 1.2 s 呼吸（reduced-motion 关） |
| a11y | `role="status" aria-live="polite"`；spinner / dot `aria-hidden` |

## 17 · BaseIconButton

#### UI 参数（来自 UI_PROMPTS §02-W）
| 类别 | 值 |
|---|---|
| 尺寸 | 32 × 32（squircle） > SPEC 前段补充：24 / 32 / 40 三档 |
| 圆角 | 10 |
| Icon | Lucide line，size 16，stroke 1.5，color `text-tertiary #8C8C82` |
| 颜色 | default bg transparent；hover bg `bg-subtle #F4F4F1`，icon `text-primary #1A1A1A`；active bg `bg-muted #EAEAE5` + `scale(.96)`；disabled icon `text-disabled #BDBDB8` + opacity 40 % |
| 焦点环 | `0 0 0 3 rgba(79,70,229,.20)` |
| 动效 | scale + bg 120 ms；reduced-motion 关 scale |
| 强制配套 | **必须 `aria-label`**；推荐配 Tooltip；toggle 模式 `aria-pressed` |
| 示例 | 🔔 Notify / 🌐 i18n / ⋯ kebab / 🔍 Search / ⤢ Expand |

---

# 统一参数表

## 圆角统一表

| 组件 | radius |
|---|---|
| chip / badge | 6 |
| icon-button | 10 |
| button / input | 10 |
| card / popover / drawer (inset) / toast 顶面（PROMPTS=14 → 采用 SPEC=16） | 14 |
| toast | 16 |
| modal / big panel | 20 |
| status-pill / progress track / avatar / tag link / drawer attached-side | 999 / 0 |

## 阴影统一表

| 层级 | token / 规格 | 用途 |
|---|---|---|
| sm | `0 1 2 rgba(15,15,20,.04)` | card flat、slider thumb |
| md | `0 4 12 rgba(15,15,20,.06)` | 抬起 card、popover |
| lg | `0 12 32 rgba(15,15,20,.10)`（PROMPTS）/ `.12`（SPEC，toast 用） | modal、drawer、toast |
| focus | `0 0 0 3 rgba(79,70,229,.20)` | 所有可聚焦控件 a11y 焦点环 |

## z-index 层级表

| 段位 | 值 | 组件 |
|---|---|---|
| base | 0 | 常规文档流 |
| sticky | 100 | 顶栏 sticky / dropzone sticky |
| popover (legacy dropdown) | 1000 | 普通下拉 / Naive 默认 |
| drawer | 2000 | BaseDrawer |
| modal | 3000 | BaseModal（默认 trap 层） |
| popover (modal-layer) | 3100 | floating-vue popover 上层 |
| tooltip | 3200 | BaseTooltip |
| toast | 4000 | BaseToastViewport（最上层但不抢焦点） |
| cmdk | 3000 + 50 = 3050（建议） | M3 CommandPaletteOverlay，置于 modal 与 popover 之间 |

## 动效阈值统一表

| 维度 | 值 |
|---|---|
| hover / focus | 120 ms ease-out |
| modal / drawer enter | 200 ms cubic-bezier(.2,.8,.2,1) |
| modal / drawer exit | 200 ms 同曲线 |
| tooltip enter delay | 240 ms |
| tooltip dismiss | 120 ms |
| popover enter | 120 ms（opacity + scale .98 → 1） |
| skeleton 触发阈值 | pending ≥ 800 ms 才显示 |
| skeleton min visible | 300 ms |
| skeleton shimmer | 1.2 s loop |
| progress determinate | width 200 ms ease-out |
| progress linear indeterminate | 1.4 s ease-in-out infinite |
| progress ring indeterminate | 1 s linear |
| toast enter / exit | 200 ms / 120 ms |
| toast auto-dismiss | success 4 s / info 5 s / warning 6 s / danger ∞ / action ≥ 10 s |
| streaming caret | 22 ms / token，闪烁 1.0 Hz |
| KG node settle | 320 ms spring |
| page transition | 240 ms ease |

## 关键冲突一览（PROMPTS vs SPEC，统一采用 SPEC）

1. Modal 蒙层透明度：PROMPTS `.40` / SPEC `.45` → **采用 .45**
2. Drawer 宽度档：PROMPTS 360/440/800 / SPEC 480/640/880 → **采用 SPEC**
3. Tooltip 背景：PROMPTS `#1A1A1A` / SPEC `#1A1B22` → **采用 SPEC**
4. Toast 圆角：PROMPTS 14 / SPEC 16 → **采用 16**
5. Toast 阴影 alpha：PROMPTS `.10` / SPEC `.12` → **采用 .12**
6. Toast danger 色：PROMPTS `#EE4444` / SPEC `#E5484D` → **采用 SPEC**
7. Skeleton 色：PROMPTS gradient（bg-muted → bg-subtle）/ SPEC 单色 `#ECECE8` → **采用 PROMPTS gradient**（更接近真实 shimmer 视觉）
