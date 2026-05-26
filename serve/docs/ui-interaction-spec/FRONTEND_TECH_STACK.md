# 前端技术栈方案 — RAG-KG Copilot

> 综合 `docs/ui-interactions/01–08` 八份组件级 UX 与实现分析报告整合而成。
> 与 `PROJECT_OVERVIEW.md §14` 的既有约束（Vue 3.4+ + Pinia + Naive UI 薄包装 + UnoCSS + ECharts + Cytoscape + vue-i18n + openapi-typescript）兼容；本表给出**为什么这样选**与**新增辅助库的取舍**。

---

## 0. 选型原则（不可破）

1. **业务层禁止直接 import Naive UI 原子**，全部经 `components/base/*` 薄包装。Naive 是实现细节，未来可换。
2. **设计 Token 是唯一颜色源**。禁止 hex 字面量；用 UnoCSS theme key + CSS variable；ESLint + Stylelint 双重拦截。
3. **URL 即状态**。所有可分享的状态进 query string（filter / focus / depth / onboarding=1 / taskId）。切库 = `router.push` + `libraryStore.$reset` 广播给所有 library-scoped store。
4. **类型自动化**。`openapi-typescript` 从 `/openapi.json` 生成 DTO；前端不手写 API 类型。表单 schema 用 `zod`，与生成的 DTO 对齐。
5. **A11y / i18n / 动效是约束而非装饰**：focus ring 3 px / `prefers-reduced-motion` / 双语 key 集合一致（`pnpm i18n:check`）/ aria-live 流式必须节流 ≥ 250 ms。

---

## 1. 核心运行时

| 用途 | 选型 | 版本 | 理由 |
|---|---|---|---|
| 框架 | **Vue 3.4+** Composition API | `^3.4` | `<script setup>` + defineModel + Suspense 已稳 |
| 构建 | **Vite 5** + `@vitejs/plugin-vue` | `^5` | 与 UnoCSS / openapi-typescript / Vitest 生态最顺 |
| 类型 | **TypeScript strict** | `^5.4` | `noUncheckedIndexedAccess` 必开；禁 `any`，外部输入 `unknown` |
| 路由 | **Vue Router 4** | `^4.3` | scrollBehavior + named views + meta guard |
| 状态 | **Pinia** | `^2.1` | `defineStore` setup 风格；用 `pinia-plugin-persistedstate` 持久化 UI 偏好 |
| i18n | **vue-i18n@9** | `^9.10` | composition API；`@intlify/unplugin-vue-i18n` 编译 message |
| HTTP | **`@microsoft/fetch-event-source`** + 原生 `fetch` | `^2.0` | 原生 `EventSource` **不支持 POST / Authorization header**，本项目 SSE 必备 |

> 不引入独立 axios。`fetch` + 一个 `useApi()` composable（重试 / Retry-After / 错误码归一化）足够。

---

## 2. 设计系统层（atoms / 展示原子）

### 2.1 UI 原语库

**保留 Naive UI** 作为底座，但严格走 `components/base/*` 包装层。理由：
- 与 Cobalt Lab 暖灰 + 钴蓝紫的色系适配成本低（暴露 `themeOverrides`）
- 表单 / 表格 / 弹层 / 树 / 步骤 / 抽屉等关键原语齐全且活跃维护
- TS 类型完善

### 2.2 浮层 / 弹出 / Tooltip

| 选型 | 用在哪 | 不选 X 的原因 |
|---|---|---|
| **floating-vue**（首选）或 `@floating-ui/vue` 自封装 | CitationChip hover preview、Mention dropdown、SideNav 折叠态浮出、KG 节点 tooltip、Composer slash command | Naive 的 `n-popover` 与设计图视觉差异较大；`floating-vue` 的 placement 算法、`safePolygon` 防 hover jitter 更稳 |

⚠️ **冲突警告**：floating-vue + Naive 的 z-index 体系并存。约定：
- Naive 原生组件用其默认层级（`z-index: 3000~6000`）
- floating-vue 自封装统一在 `z-popover: 7000 / z-modal: 8000 / z-toast: 9000`，写进 UnoCSS theme `zIndex`

### 2.3 动效

| 库 | 用途 |
|---|---|
| **`@formkit/auto-animate`** | 列表增删（SessionList / LiveCitationList / Chip 列表）零配置过渡 |
| **`@vueuse/motion`** | 进/退场（Modal / Drawer / Toast / Banner）声明式 spring；尊重 `prefers-reduced-motion` |
| 原生 CSS transition | 单状态切换（hover / focus）— 120 ms ease-out |

> 不引入 GSAP / motion-one — 体积与心智负担过大，`@vueuse/motion` 足够。

### 2.4 焦点 / 键盘 / 拖拽

| 库 | 用途 |
|---|---|
| **`@vueuse/core`** | `useFocusTrap` / `useMagicKeys` / `useScroll` / `useStorage` / `useDropZone` / `useTextareaAutosize` / `useIntersectionObserver` / `onClickOutside` |
| **`vuedraggable@4`** | QualityKPIPanel 拖拽重排；SessionList 排序 |

---

## 3. 表单与数据校验

| 库 | 用途 |
|---|---|
| **`vee-validate@4`** + **`zod`** | LibraryCreateModal / BudgetSettingsForm / SchemaEditor 全部表单 |
| **`@vee-validate/zod`** | 把 zod schema 适配到 vee-validate |
| **`openapi-typescript`** | 由 `/openapi.json` 生成 TS 类型，zod schema 与之 cross-check |

约束：每个表单都有 zod schema；zod 字段与生成 DTO 字段对齐（CI 检查）。

---

## 4. 表格 / 列表

| 库 | 用途 | 选它而非 X 的原因 |
|---|---|---|
| **`@tanstack/vue-table`** | DocumentRow 表（S6）/ FailureCaseTable（S8）/ Eval 数据表 | headless = 视觉完全交 Cobalt token 控制；sort / filter / grouping / pinning / column resize 内置；不让第三方 UI 库劫持设计；与 `vue-virtual-scroller` 组合即可处理大数据 |
| **`vue-virtual-scroller`** | 行 > 200 时启用；SessionList > 100 时启用；长 markdown 消息列表 | 比 `vue-virtual-list` 维护活跃；fix-height & dynamic-height 均支持 |

> 不用 `n-data-table` 做核心表格：风格定制成本高，与 UnoCSS token 解耦困难；保留它用于设置页等次级表格。

---

## 5. 聊天 / 流式 / 引用

| 库 / 模式 | 用途 |
|---|---|
| **`@microsoft/fetch-event-source`** | SSE 客户端（支持 POST + Authorization） |
| 自写 **`useSSEChat(sessionId)`** composable | 解析 `meta / token / citations / done / error` 五事件路由 |
| 自写 **`useTokenStream()`** | rAF 节流的打字机；尊重用户向上滚动则停 autoscroll |
| **`markdown-it`** + **`markdown-it-shiki`** + **`katex`** | Markdown 渲染；自定义 rule 把 `[id]` 编译成 `<CitationChip>` Vue 组件 |
| 自写 **`useCitationFilter()`** | 渲染期 whitelist 过滤 — 不在 `citations[]` 的 `[id]` 静默删除（防 LLM 幻觉） |
| **`@floating-ui/vue`** | Composer 的 `@mention` / `/command` 下拉，光标位置锚定（IME 友好；不用 `tribute.js`） |

**单 SSE 多 subscriber 抽象**（长任务）：自写 `useTaskStream(taskId)`，按 `taskId` ref-count GC，PipelineTree / RunStats / LiveCitationList / DraftStream 四组件共享同一连接；`tasksStore` 持有连接所有权，组件 unmount 不断流，让"后台运行"成为零成本。

---

## 6. 知识图谱（KG）

| 库 | 何时用 | 理由 |
|---|---|---|
| **Cytoscape.js** + `cytoscape-fcose` + `cytoscape-popper` + `cytoscape-cxtmenu` + `cytoscape-edgehandles` | 默认（50–3000 节点） | 插件生态最全；selector + style 与 Cobalt token 直接对齐；首屏渲染稳；与 `floating-vue` 用 popper 同源 |
| **`cytoscape-dagre`** | S7 跨文献推理的路径横向布局 | 路径图（A→r1→B→r2→C）用 DAG 布局比力导向更可读 |
| **sigma.js**（lazy import） | > 3000 节点 自动降级 | WebGL 渲染；> 10k 节点进 community 聚类后再渲染 |

**reactivity 边界**：节点数据用 `shallowRef`，不让 Vue reactivity 深入 Cytoscape 内部；Cytoscape 实例放在 `markRaw()` 中。

**不选**：
- `vue-flow` — workflow editor 定位，每节点一个 DOM，密集图卡顿
- `antv/g6` — Vue 桥需自己维护
- `v-network-graph` — SVG 上限低
- ECharts graph series — 自定义交互能力弱

---

## 7. 图表 / 数据可视化

| 库 | 用途 |
|---|---|
| **ECharts 5** + **`vue-echarts`** | KPI Card sparkline / TrendBarChart / EvidenceTimeline (custom series) / Eval 趋势 |
| 纯 SVG（自写） | CostMeter 环、Progress Ring、Hypothesis 三轴 mini chart — 体积省 90 KB |
| **`date-fns`**（不引 dayjs） | `formatRelative` / `formatDistance` / locale；避免双时间库 |

按需引入 ECharts 组件（`use([BarChart, LineChart, GaugeChart, ...])`）控制 bundle 体积。

---

## 8. PDF / 文档预览

| 库 | 用途 |
|---|---|
| **`vue-pdf-embed`** 或直用 **`pdfjs-dist`** | M4 DocumentDetailDrawer 的 PDF 预览（高亮 chunk 区域） |
| **Monaco Editor**（`@guolao/vue-monaco-editor`） | SchemaEditor 的 JSON / YAML / Visual 三视图同步 |

> 不引入 CodeMirror — 已经有 Monaco 就别两套编辑器并存。

---

## 9. 命令面板 / 快捷键 / 工具栏

| 库 | 用途 |
|---|---|
| 自封装 **`useCmdK()`** composable + 自渲染 list | ⌘K CommandPaletteOverlay；使用 **`fuse.js`** 做模糊匹配 |
| **`@vueuse/core` `useMagicKeys`** | 全局快捷键（⌘O 切库 / ⌘N 新建 / `/` 聚焦搜索 / `g d` jump-to-Docs / Esc 关闭浮层） |
| 自写 **`useShortcut(scope)`** | scope 化分发（避免 chat 输入框吃了全局 `/`） |

> 评估过 `cmdk-vue`：当下 API 不稳，体积 vs 收益不划算，自写。

---

## 10. 文件上传 / 拖拽

| 库 | 用途 |
|---|---|
| `@vueuse/core` `useDropZone` + 自写队列 | S6 DropZone；SHA-256 客户端预算（webcrypto）后 POST；重复 → "已存在"非错 |
| **`file-type`** | 客户端 magic bytes 校验（不只 mime） |

---

## 11. 测试

| 层 | 工具 |
|---|---|
| 单元 / 组件 | **Vitest** + **`@vue/test-utils`** + **`@testing-library/vue`**（user-event 风格） |
| E2E | **Playwright**（5 条核心 journey：建库→上传→提问→综述→评测面板） |
| 视觉回归 | **Playwright `expect.toHaveScreenshot()`** — 关键屏（S3 三态 / S4 / S5 进行中） |
| A11y | **`@axe-core/playwright`** 在 E2E 中跑（critical violations = 0） |

约束：`components/base/*` 覆盖率 ≥ 80%。

---

## 12. Bundle / 性能

| 工具 | 用途 |
|---|---|
| `vite-plugin-inspect` + `rollup-plugin-visualizer` | 包体监控；目标：首屏 JS ≤ 300 KB（gz） |
| Route-level code split | `S4 KG / S5 Review / S7 Reason / S8 Eval` 全部按需加载 |
| **Suspense** + Skeleton | 异步组件统一 fallback |
| **`@vueuse/head`** 或 `@unhead/vue` | document.title / og 元数据 / lang attr 切换 |

---

## 13. 完整 `package.json` 依赖建议（dependencies）

```jsonc
{
  // 核心
  "vue": "^3.4",
  "vue-router": "^4.3",
  "pinia": "^2.1",
  "pinia-plugin-persistedstate": "^3.2",
  "vue-i18n": "^9.10",

  // UI 底座
  "naive-ui": "^2.38",
  "@unocss/preset-uno": "^0.58",

  // 浮层 / 动效
  "floating-vue": "^5.2",
  "@floating-ui/vue": "^1.0",
  "@formkit/auto-animate": "^0.8",
  "@vueuse/motion": "^2.1",

  // utils / a11y / keyboard
  "@vueuse/core": "^10.9",
  "@vueuse/head": "^2.0",

  // 表单
  "vee-validate": "^4.12",
  "@vee-validate/zod": "^4.12",
  "zod": "^3.22",

  // 表格 / 虚拟列表
  "@tanstack/vue-table": "^8.13",
  "vue-virtual-scroller": "^2.0.0-beta.8",
  "vuedraggable": "^4.1",

  // SSE / 流式
  "@microsoft/fetch-event-source": "^2.0",

  // Markdown / 代码
  "markdown-it": "^14",
  "markdown-it-shiki": "^0.9",
  "shiki": "^1.3",
  "katex": "^0.16",

  // 图表 / KG
  "echarts": "^5.5",
  "vue-echarts": "^6.7",
  "cytoscape": "^3.28",
  "cytoscape-fcose": "^2.2",
  "cytoscape-dagre": "^2.5",
  "cytoscape-popper": "^4.0",
  "cytoscape-cxtmenu": "^3.5",
  "cytoscape-edgehandles": "^4.0",
  "sigma": "^3.0",

  // PDF / 编辑器
  "vue-pdf-embed": "^2.0",
  "@guolao/vue-monaco-editor": "^1.5",

  // 命令面板 / 搜索
  "fuse.js": "^7.0",

  // 时间 / 文件
  "date-fns": "^3.6",
  "file-type": "^19.0"
}
```

**devDependencies**：`typescript ^5.4` / `vite ^5` / `@vitejs/plugin-vue` / `unocss` / `unplugin-vue-components` / `@intlify/unplugin-vue-i18n` / `vitest` / `@vue/test-utils` / `playwright` / `@axe-core/playwright` / `openapi-typescript` / `@types/markdown-it` / `eslint` + `@antfu/eslint-config` / `stylelint` + `stylelint-config-recess-order`。

---

## 14. Pinia store 划分

| Store | 职责 |
|---|---|
| `libraryStore` | 当前 / 全部 / 最近 / pinned；切库广播 `$reset` 给其他 lib-scoped store |
| `chatStore` | 会话列表 + 消息 + 流式状态 + citation 索引 |
| `evidenceStore` | activeCitationId / pinned evidence / preview cache |
| `kgStore` | filter / focus / depth / 节点边缓存（shallowRef）|
| `taskStore` | 长任务（review / reason / hypothesize）订阅与归一化事件流 |
| `settingsStore` | LLM router / embedder / budget / schema / 主题 |
| `costStore` | 实时成本与上限 — 硬墙判定（exceeded → 全局 disable expensive actions） |
| `colorStore` | entity_type / relation_type 颜色 — 单一源，SchemaEditor 改色 5 ms 内 KG / PathViz / LibraryCard 全部热更 |
| `notificationStore` | 通知铃数据 + SSE 推送 |
| `commandPaletteStore` | ⌘K 状态、recent、suggestion |
| `uiStore` | sidenav 折叠 / 当前 theme / drawer pin |

---

## 15. 全局 composables

| Composable | 用途 |
|---|---|
| `useSSEChat(sessionId)` | Chat 流式 |
| `useTaskStream(taskId)` | 长任务多 subscriber |
| `useTokenStream()` | rAF 节流打字机 + 智能 autoscroll |
| `useAsyncResource(fn)` | Skeleton → Data / Empty / Error 统一状态机（minVisibleMs + skeletonAfterMs 防 flash） |
| `useCmdK()` | 命令面板 |
| `useShortcut(scope)` | scope 化键盘 |
| `useToast()` | 顶部右 toast 队列（替代 n-message，可控 a11y `role=status`） |
| `useFocusStack()` | 全局焦点 trap 栈（Modal/Drawer 嵌套时 pin/pop） |
| `useLibraryGuard()` | 切库前的 unsaved-changes 拦截 |
| `useCostGuard()` | expensive action 前的 budget 检查 |

---

## 16. 与已有 PROJECT_OVERVIEW §14 的差异

| 项 | 既定 | 本方案 | 说明 |
|---|---|---|---|
| 表格 | 未明 | `@tanstack/vue-table` | 让 Cobalt token 控制视觉 |
| 浮层 | 未明 | `floating-vue` + 自封装 | 与 Naive 共存，统一 z-index |
| 表单 | 未明 | `vee-validate` + `zod` | 与 openapi-typescript 配对 |
| SSE | 未明 | `@microsoft/fetch-event-source` | 原生 EventSource 不支持 POST |
| Markdown | 未明 | `markdown-it` + 自定义规则 → CitationChip | 渲染期 whitelist 过滤 |
| 命令面板 | 未明 | 自封装 + `fuse.js` | `cmdk-vue` 不成熟 |
| 编辑器 | 未明 | Monaco | SchemaEditor 三视图 |
| PDF | 未明 | `vue-pdf-embed` / `pdfjs-dist` | DocumentDetailDrawer |
| KG fallback | 未明 | sigma.js（lazy） | > 3000 节点 WebGL 降级 |

---

## 17. 一句话风险点

> **floating-vue 与 Naive UI 的层级体系需手动协调**，建议把 `n-popover / n-dropdown / n-tooltip` 在 base 包装层全部转译到 floating-vue，长期收敛为单一浮层栈，避免 Modal 内 popover 被遮挡这种典型 bug。
