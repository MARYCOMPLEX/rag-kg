# KG Browser 交互规范 (S4 `/lib/:id/kg`)

> 配套设计稿：`docs/ui-images/039-03-p-kg-canvas.png` · `040-03-q-kg-node.png` · `041-03-r-kg-edge.png` · `042-03-s-kg-filter-panel.png` · `043-03-t-entity-detail-drawer-in-kg-view.png`
> 调色板：`schema.color_palette`（12 色 colorblind-safe，Cobalt Lab token：`--kg-cat-1..12`）
> 数据：`GET /api/v1/graph/:libId/neighborhood?focus=&depth=1..3&types=&relations=&conf>=`
> 设计目标：**密集学术图 + 邻域聚焦 + 与 Chat / Evidence / Reasoning 深度联动**

---

## 0. 库选择评估（最重要的架构决定）

### 0.1 横向对比

| 维度 | **Cytoscape.js** | sigma.js | AntV G6 | v-network-graph | Vue Flow |
|---|---|---|---|---|---|
| 节点上限（流畅 60fps） | 1.5k Canvas / 5k+ WebGL ext | **20k+ WebGL 原生** | 3k Canvas / 10k+ G6X | 500–1k SVG | 300 SVG/DOM |
| 力导向质量 | fcose/cola/d3-force 全支持 | 仅 forceAtlas2 | force/dagre/concentric 全 | 内置 d3-force | 不提供（手摆） |
| 自定义渲染（节点/边） | CSS-like style + canvas renderer | **WebGL 程序级**，门槛高 | React/Canvas/G | SVG slots，灵活 | DOM/React 强，但每节点 = DOM |
| TS 支持 | 一级（@types/cytoscape） | 一级 | 一级 | 一级 | 一级 |
| Vue 3 集成成本 | 包一层 `KGCanvas.vue` 即可，社区 `vue-cytoscape` 偏旧不必用 | 同 Cytoscape，需手写 | 需 G6 + Vue 桥 | **原生 Vue 3 组件** | **原生 Vue 3** |
| 上下文菜单 / 框选 | 一等公民（cytoscape-cxtmenu / cytoscape-edgehandles） | 需自建 | 内置 | 部分 | 部分 |
| 布局热替换 | layout.run() 平滑 | 需手控 | 内置过渡 | 内置过渡 | 不适合 |
| SSR | N/A（客户端渲染） | 同 | 同 | 同 | 同 |
| 学术图典型场景适配 | **★★★★★** | ★★★★（超大图） | ★★★★ | ★★★ | ★ |
| Bundle 体积（gz） | ~110 kB + 插件 | ~60 kB | ~200 kB | ~70 kB | ~80 kB |

### 0.2 推荐：**Cytoscape.js（生产主用） + sigma.js 大图 fallback**

理由：
1. KG 浏览器**首屏 = 邻域 50–200 节点**（设计稿"top 50 shown"），Canvas 渲染足够，调试体验最佳。
2. Cytoscape 的 **selector + style 语法** 与 Cobalt Lab token 对齐成本最低（直接写 `node[type="Concept"]` { background-color: var(--kg-cat-1) }）。
3. 插件生态：`cytoscape-cxtmenu`（右键菜单）/ `cytoscape-fcose`（高质量力导向）/ `cytoscape-edgehandles`（手动连边）/ `cytoscape-popper`（tooltip 联动 Floating UI）一站齐备。
4. 当 `nodes.length > 3000` 自动降级到 **sigma.js + graphology** WebGL 渲染（lazy import，避免首屏占用 60 kB）。
5. **不选 vue-flow** 因其定位为 workflow / node-editor，每节点 DOM，密集图 300 节点已抖动；不选 G6 因 Vue 桥额外维护成本 + bundle 偏大；不选 v-network-graph 因 SVG 上限在 1k 左右、力导向算法弱。

### 0.3 包装层

```
KGCanvas.vue           # 引擎适配器，根据 engine prop 选择
├── adapters/
│   ├── cytoscapeAdapter.ts   # 默认
│   └── sigmaAdapter.ts       # >3k 节点 lazy
└── KGCanvas.types.ts         # IGraphEngine 接口（add/remove/select/focus/exportPng）
```

视图层永远只调 `IGraphEngine`，引擎可换。

---

## 1. KGCanvas（画布主体，对应 039）

### 视觉
- 容器：圆角 16 px，1 px `--border-soft` 描边，内边距 0；右上角浮层工具栏（Fullscreen / Re-layout / Export / API view）。
- 背景：纯白 `--bg-canvas`，**禁用网格**（学术图加网格干扰阅读）；可选 8 px dot pattern（toggle）。
- 焦点节点："Graph Retrieval" 居中，2 px `--accent-primary` 描边 + 12 px 软阴影。
- 邻居环：默认 8 邻居，半径自适应（`min(width, height) * 0.35`）。
- 底部状态条：`8,491 entities (top 50 shown) · 31,219 triples · confidence ≥ 0.65`，12 px secondary 文字。
- 右下角图例：六个 type 圆点 + 名称，点击 = 临时筛选该 type。

### 状态
| 状态 | 表现 |
|---|---|
| empty | 居中插图 + "No entities yet — index documents first" + CTA `Open Library` |
| loading | skeleton 圆点 + 灰边，骨架 1.2 s 后转 spinner，>3 s 显示"Layout is computing 1.2k nodes" |
| ready | 力导向稳态 |
| degraded（>3k） | 顶部 banner "Large graph: switched to WebGL renderer" |
| error | 居中错误卡 + Retry，错误码显示在 Toast |

### 交互（**这是必须穷尽的部分**）

#### 1.1 鼠标
| 手势 | 行为 |
|---|---|
| 空白拖拽 | 平移视口（cy.userPanningEnabled = true） |
| 滚轮 | 缩放；`Ctrl/Cmd + 滚轮` = 高精度缩放（系数 0.05） |
| 双击空白 | Fit to viewport（cy.fit(null, 40)） |
| 单击节点 | 选中（加 `.selected` class）+ 打开 EntityDetailDrawer + URL `?focus=eid` |
| 双击节点 | 聚焦邻域（重新 fetch depth=1, 动画 600 ms 重布局） |
| 右键节点 | cxtmenu：Expand 1-hop / Hide / Pin / Copy ID / **Cite in Chat** / Find paths from here |
| 右键边 | cxtmenu：Show evidence / Hide / Cite this triple |
| Hover 节点 | tooltip（Floating UI，offset 12 px）+ **1 度邻居高亮**：自身 `.hover`，邻居 `.neighbor`（边框加粗），**其余降 opacity 0.3**（**不是全部变暗**） |
| Shift + 拖拽 | 矩形框选（cytoscape-box-select），多节点选中后右键菜单出现 "Collapse to cluster" |
| 拖拽节点 | 仅在 `pinned` 模式下生效；普通模式自动重新进入力导向 |

#### 1.2 触屏
- 单指拖 = 平移；双指 pinch = 缩放；双指旋转 = 忽略（学术图不允许斜视）。
- 长按节点 600 ms = 上下文菜单。
- 双击 = focus；三指点 = 全屏切换。

#### 1.3 键盘（A11y 核心）
| 键 | 行为 |
|---|---|
| ← / → / ↑ / ↓ | 平移 40 px |
| `+` / `-` | 缩放 1.2x / 0.83x |
| `0` | Fit |
| `Esc` | 取消选择 + 关 drawer + 关 cxtmenu |
| `Cmd/Ctrl + A` | 选中可见节点 |
| `Cmd/Ctrl + F` | 焦点跳到 FilterPanel 搜索框 |
| `Tab` | 在节点间依次 focus（按 degree 排序），announce 通过 aria-live |
| `Enter` | 对当前 focus 节点等同于单击 |
| `Shift + Enter` | 展开邻居 |
| `Cmd/Ctrl + E` | 导出 PNG |
| `Cmd/Ctrl + L` | 复制可分享 URL（含 filter/focus/depth/viewport） |

#### 1.4 性能阈值
| 节点数 | 渲染 | 布局 | 标签 |
|---|---|---|---|
| 0–500 | Canvas 默认 | fcose 完整 | 全显 |
| 500–2000 | Canvas + `textureOnViewport: true` + `motionBlur: true` | fcose quality=draft | zoom > 0.5 才显 |
| 2000–3000 | Canvas + batch render（cy.startBatch() 内 add） | cola | 仅 selected/hover |
| > 3000 | **降级 sigma.js WebGL**，节点 5×5 px 点 | forceAtlas2 worker | hover/选中才显 |
| > 10000 | **聚类抽样**：按 community detection 合成超节点，双击展开 |

### A11y
- canvas 外层 `role="application" aria-label="Knowledge graph for {libraryName}"`，承担键盘焦点。
- 与画布并列一个 `<ul role="listbox" class="sr-only">` 节点列表镜像，screen reader 可遍历。
- aria-live="polite" 区域 announce "Focused: GraphRAG, Concept, 12 neighbors"。
- 颜色编码同时给 **icon + 形状**（Method 六边形 / Dataset 方形 / Concept 圆 / Metric 三角 / Author 圆带头像位 / Venue 菱形），不依赖纯颜色。
- 提供高对比模式：在 `prefers-contrast: more` 下边框增至 2 px，标签字体加粗。
- focus ring 用 2 px outline + 2 px offset，符合 WCAG 2.2 AA。

### 动效
- 布局过渡：`cy.layout({ animate: true, animationDuration: 480, animationEasing: 'ease-out-quart' })`。
- 节点出现：scale 0.6 → 1，opacity 0 → 1，280 ms stagger 12 ms。
- Hover 高亮：opacity 230 ms ease-out，边框宽度 180 ms。
- 选中：2 px → 3 px 描边 + 6 px 软阴影，220 ms。
- `prefers-reduced-motion`：全部 ≤ 80 ms 或瞬时。

### Vue 实现
```ts
// KGCanvas.vue 关键 ref（草图，非全代码）
const containerRef = ref<HTMLDivElement>()
const engine = shallowRef<IGraphEngine>()      // 不让 Vue 深响应 Cytoscape 内部！
const elements = shallowRef<ElementDefinition[]>([])
const selectedIds = ref<Set<string>>(new Set())
const hoveredId = ref<string | null>(null)
const viewport = ref<{ zoom: number; pan: { x:number; y:number } }>(...)

const { filter, focus, depth } = useKGRouteQuery()       // URL <-> state
const { data, isFetching } = useNeighborhood(libId, focus, depth, filter)

watchDebounced(filter, () => engine.value?.applyFilter(filter.value), { debounce: 300 })
watch(data, (g) => engine.value?.setGraph(g))

onMounted(async () => {
  const adapter = data.value.nodes.length > 3000
    ? await import('./adapters/sigmaAdapter').then(m => m.create)
    : await import('./adapters/cytoscapeAdapter').then(m => m.create)
  engine.value = adapter(containerRef.value!, {
    onNodeClick:  (id) => { selectedIds.value = new Set([id]); openDrawer(id) },
    onNodeHover:  (id) => { hoveredId.value = id },
    onCtxMenu:    (target, type) => kgCtxMenu.open(target, type),
    onViewport:   (vp) => { viewport.value = vp; syncToUrl() },
  })
})

onBeforeUnmount(() => engine.value?.destroy())
```

### 联动
- `selectedIds` 变化 → `entityDrawerStore.open(id)` + URL `?focus=`
- 右键 "Cite in Chat" → `composerStore.appendMention({ id, label, type })` + 全局 toast
- "Find paths from here"（多选两点）→ 跳 S7 `/lib/:id/reasoning?from=&to=`
- Hover 节点 → EvidencePanel 顶部高亮该 entity 名的徽章
- Filter 变化 → URL → 其他屏（如 Chat）刷新时仍能继承

### UI 参数（来自 UI_PROMPTS §03-P）

| 类别 | 值 |
|---|---|
| 画布容器 | 800 × 844，radius `card` 14，bg `bg-surface` #FFFFFF，1 描边 `border-subtle` #E4E4E0，padding `--space-24` 24 |
| 标题行 | h3 20/24.2 600 "Knowledge graph · {libSlug}" |
| 工具栏图标 | Lucide line stroke 1.5，icon 16；按钮组：fit / rotate-ccw / image-down / code |
| 工具栏对齐 | 右对齐，与标题同行（与既有"右上角浮层工具栏"冲突 —— PROMPTS 为同行右对齐，文档主体描述为浮层；以 PROMPTS 为准） |
| 背景 | bg `bg-surface` #FFFFFF |
| Dot-grid | 12% 透明度，dot 颜色 `bg-muted` #EAEAE5；间距 — |
| 边线（默认） | 1 curved bezier，`border-subtle` #E4E4E0，opacity 30% |
| 箭头头部 | 6 × 6 chevron，位于 target 端 |
| 边标签（hover） | body-sm 13/15.7 400 `text-tertiary` #8C8C82 |
| 选中节点强调 | brand-500 #4F46E4 描边环 + brand-50 #EDF0FF 内发光 |
| 底部视图统计 | caption 12/14.5 400，左下；文本 "8,491 entities (top 50 shown) · 31,219 triples · confidence ≥ 0.65" |
| 图例 | 右下角，6 dots + 类型名 body-sm 13/15.7 400 |
| 性能切换 toast | "Large graph: switched to WebGL renderer"（节点 > 3000 时顶部 banner） |
| Zoom 显示位置 / 字号 | — |
| Fit 按钮位置 | 工具栏首位（与标题同行右对齐） |

---

## 2. KGNode（对应 040）

### 视觉编码（多通道，不只靠颜色）
- **颜色** = entity_type（12 色 palette；alpha 12% 填充 + 100% 描边 + 100% 文字色）
- **形状** = entity_type 副通道：Concept 圆 / Method 六边形 / Dataset 矩形 / Metric 三角 / Author 圆 + 头像 slot / Venue 菱形
- **大小** = degree centrality 归一化：`r = 9 + 15 * sqrt(degree/max)`，限制 18–48 px
- **边框** = 状态：default 1.5 px / hover 2 px / selected 3 px primary / pinned 2 px dashed / focused 3 px + glow
- **双圈环** = 在当前 Chat 引用过：外层 ring 2 px `--accent-primary` offset 3 px
- **标签** = 节点下方 6 px 间距，11 px medium，前 24 字符 + "…"；hover 全显（最长 40 字符再 wrap）
- **zoom < 0.6** 全部标签隐藏，仅 selected/hover 显
- **zoom < 0.3** 节点缩为 4 px dot，标签全隐
- **置信度** < 0.5 节点：dashed 边框，alpha 60%

### 状态
default / hover / selected / pinned / focused / cited（双圈）/ filtered-out（opacity 0.15，no events）/ ghost（被 hover 邻居降透时）

### 交互
单击选 / 双击 focus / 右键菜单 / 拖拽（pinned 模式）/ Hover tooltip + 邻居高亮

### A11y
每个节点对应一个 sr-only `<li tabindex="-1" role="option" aria-selected>` 节点；Tab/Enter 等同鼠标。

### 动效
出现 stagger 12 ms；degree 变化时半径 240 ms ease-out；选中描边 180 ms。

### Vue 实现
```css
/* style block 由 cy.style() 注入；不入 Vue 模板 */
node[type='Concept']  { shape: ellipse;    background-color: var(--kg-cat-1); ... }
node[type='Method']   { shape: hexagon;    background-color: var(--kg-cat-2); ... }
node.cited            { border-color: var(--accent-primary); border-width: 2; ring: 2 ... }
node.ghost            { opacity: 0.3; }
```

### 联动
"cited" class 由 `composerStore.mentions` watch 同步加减。

### UI 参数（来自 UI_PROMPTS §03-Q）

| 类别 | 值 |
|---|---|
| 形态 | pill，radius `pill` 999；填充 `<type>/50`，1 描边 `<type>/500` @50%，文字 `<type>/700` |
| 文字 | body-sm 13/15.7 600 |
| 内边距 | 8 / 14（垂直 / 水平） |
| 宽度 | 由 label 自适应；高度 36–52（按 label 行数） |
| 前导 dot | 8 × 8，颜色 `<type>/500` |
| 节点最小 / 最大 | 18 / 48（PROMPTS 未直接写，源自 SPEC 主体；与 PROMPTS pill 高度 36–52 不冲突，pill 高度独立于"节点圆形直径"） |
| size 映射 | `r = 9 + 15 * sqrt(degree / max)`，clamp [18, 48] |
| 默认描边 | 1.5 `<type>/500` @50%（PROMPTS 写 1，文档主体写 1.5；以 1.5 为准，PROMPTS 1 标注冲突） |
| selected 描边 | 2 brand-500 #4F46E4 + shadow-md `0 4px 12px rgba(15,15,20,.06)`（PROMPTS 2；文档主体写 3，冲突 —— 以 PROMPTS 为准） |
| pinned 双圈 | 2 dashed；当节点已在 Chat 引用过时另加外圈 ring 2 brand-300 #8D9FFF offset 3 |
| 标签字号 | 11/13.3 Medium Inter |
| 标签 max-width | 前 24 字符 + "…"；hover 全显，最长 40 字符再 wrap |
| 标签隐藏 | zoom < 0.6 全隐；zoom < 0.3 节点缩为 4 dot |
| hover 一度高亮 | self + 邻居 opacity 1.0；其余 opacity 0.30 |
| disabled（filtered out） | opacity 30% + grayscale；事件禁用 |
| hover bg | `<type>/100` |
| 形状（多通道） | Concept 圆 / Method 六边形 / Dataset 圆角矩形 / Metric 三角 / Author 圆+头像位 / Venue 菱形 |
| 置信度 < 0.5 | dashed 边框 + opacity 60% |

---

## 3. KGEdge（对应 041）

### 视觉编码
- **颜色** = relation_type（与 entity 同 palette 但偏移 0.4 lightness，避免与节点撞色）
- **粗细** = `evidence_count`：`w = 1 + 1.4 * sqrt(count)`，范围 1–6 px
- **方向** = 三角箭头，size = stroke × 2.5
- **曲线** = bezier，control distance 30；同源同目标多边按 unbundled-bezier 自动散开
- **标签**（关系名）默认隐藏 → hover 边时浮气泡（`uses_method` / `evaluates_on`）
- **selected** = 2 px 加粗 + `--accent-primary` 着色 + 标签气泡常显 + 旁边再显第一条 evidence snippet（≤ 80 字 + "show 47 more"）
- **置信度低**（<0.5）= dashed
- **inferred 边**（推理生成，非原始三元组）= 双线 + tag "inferred"

### 状态
default / hover（粗 2 px 显标签）/ selected（粗 2.5 px + 气泡 + snippet）/ ghost（opacity 0.15）/ highlighted（被详情抽屉关系条目反查时，pulse 2 次）

### 交互
- Hover：边变粗 + 显示 relation label
- 单击：选中边 → drawer 切到 "edge mode"（展示 triple + evidence list）
- 右键：Show evidence panel / Hide / Cite this triple in Chat
- 双击边端点：相当于聚焦该节点

### A11y
sr-only 列表里 edges 用 `<li>X — relation — Y (evidence: 12)</li>`；Tab 可遍历。

### 动效
hover 粗细 180 ms；selected 220 ms + 气泡 fade-in 160 ms。

### UI 参数（来自 UI_PROMPTS §03-R）

| 类别 | 值 |
|---|---|
| 默认粗细 | 1 curved bezier，`border-strong` #8C8C82 @40% |
| 证据数 → 粗细 | `w = 1 + 1.4 * sqrt(evidence_count)`，clamp [1, 6] |
| 箭头头部 | 8 × 8 chevron（PROMPTS §03-R）；§03-P 写 6 × 6 —— 冲突，按组件级 §03-R 为准 |
| 箭头尺寸规则 | `arrow_size = stroke × 2.5` |
| hover 粗细 | 2 brand-500 #4F46E4 |
| 选中粗细 | 2.5 brand-500 #4F46E4（PROMPTS §03-R 写 2 hover；文档主体 2.5 selected，两者并存不冲突） |
| 选中倍数 | hover ×2 / selected ×2.5（相对默认 1） |
| 关系标签字号 | mono-sm 13/20 600 `text-secondary` #515151 |
| 标签气泡 | bg `bg-surface` #FFFFFF，radius `chip` 4（PROMPTS 4；全局 chip 6 —— 局部覆盖，按 PROMPTS 4） |
| 标签气泡 padding | 2 / 6（垂直 / 水平） |
| 标签触发 | 默认隐藏，hover 边时出现；selected 时常显 |
| 选中附加 | 旁侧首条 evidence snippet（≤ 80 字 + "show N more"） |
| 置信度 < 0.5 | dashed |
| inferred 边 | 双线 + tag "inferred" |

---

## 4. FilterPanel（对应 042，左侧抽屉）

### 视觉
- 宽 280 px 固定，独立 scroll；圆角 12 px；section 之间 16 px gap。
- Sections（从上到下）：
  1. **Search entity** （搜索框，icon 左、clear icon 右）
  2. **Entity types** —— 2 列 grid，每项 = color dot + 名称 + count chip + checkbox（默认全选）
  3. **Relation types** —— multi-select chip 流式排布
  4. **Depth (k-hop)** —— 1/2/3 segmented slider，当前值高亮
  5. **Confidence ≥** —— 单滑块 0.00–1.00 step 0.05，当前值小气泡显示
  6. **Community / Cluster** —— toggle "Show communities" + 颜色由社区染色覆盖
  7. **View stats** —— 灰底卡显示 entities / triples / confidence 阈值
  8. **Actions** —— Reset filters / Export view JSON

### 状态
default / dirty（任何 filter 偏离默认，header 出 reset 红点）/ loading（每个 section disabled，骨架占位）/ saved-preset（dropdown 选预设）

### 交互
- 任一控件改变 → 300 ms debounce → fetch neighborhood → URL 同步
- Search：输入 ≥ 2 字符触发，按 label fuzzy；命中节点在画布 pulse 2 次 + 自动 pan
- Depth slider：拖动时不 fetch，松开时 fetch；预估 "this will load ~1.2k nodes"
- Reset：弹气泡确认，回到默认 filter，URL 清掉 query
- Export JSON：下载当前可见子图 + filter 元数据，文件名 `kg_{libId}_{ISODate}.json`
- 保存为 preset：name dialog → 写入 `userPrefsStore.kgPresets`

### A11y
- 整个面板 `role="region" aria-label="Graph filters"`
- 每个 section h3，颜色 dot 之外加 `aria-label` 重复 type 名
- slider 提供数字输入 fallback
- Reset 按钮 confirm 必须 Esc/Enter 可控

### 动效
section 折叠 220 ms ease；count chip 数字 tween 180 ms。

### Vue 实现
```ts
// useKGFilter.ts
export const useKGFilter = defineStore('kgFilter', () => {
  const types = ref<Set<string>>(new Set(DEFAULT_TYPES))
  const relations = ref<Set<string>>(new Set())
  const depth = ref<1|2|3>(1)
  const minConf = ref(0.65)
  const community = ref(false)
  const search = ref('')
  const toQuery = computed(() => encodeKGFilter({...}))
  return { ... }
})
// FilterPanel 用 watchDebounced(filter, 300) → kgStore.applyFilter()
```

### 联动
- 与 URL：`?types=Concept,Method&depth=2&conf=0.65&q=graphrag`
- 与 KGCanvas：通过 `kgEngine.applyFilter()`，不重 fetch（client 端 class 切换）；改 depth/types 时才请求
- 与 EntityDrawer：drawer 内点击 "Filter by this type" → 反写 filter

### UI 参数（来自 UI_PROMPTS §03-S）

| 类别 | 值 |
|---|---|
| 面板 | 280 × 844 左侧停靠；bg `bg-surface` #FFFFFF；右侧 1 `border-subtle` #E4E4E0；padding 24；section gap 24（PROMPTS 280；文档主体亦 280；radius 文档主体 12，PROMPTS 未声明） |
| Title | "Filters" h3 20/24.2 600 |
| 搜索输入 | 232 × 36（BaseSlider/Input 02-B）；前缀 Lucide "search" 14；placeholder "🔍 Search entity…" |
| Section 标题 | meta 11/13.3 500 uppercase |
| Type chips 网格 | 3 × 2，每 chip 68 × 26 radius pill |
| Chip 行内 color dot | dot `<type>/500`（直径继承 KGNode 8） |
| Chip Active | bg `<type>/50` + text `<type>/700` |
| Chip Inactive | bg `bg-subtle` #F4F4F1 + text `text-tertiary` #8C8C82 |
| count chip | — |
| Depth slider | BaseSlider 02-E，min 1 / max 3 / step 1，default 2 |
| Confidence slider | min 0 / max 1 / step 0.05，default 0.65 |
| Slider 高度 | — |
| View stats | meta + 2 行 body-sm 13/15.7 400 `text-tertiary` #8C8C82 |
| Footer 按钮 | ghost "Reset filters" + secondary "Export view JSON"（底部 footer 行，位置 = footer 左到右） |
| 重置按钮位置 | footer 左侧（与 Export 同行） |
| 行高 / padding | — |

---

## 5. EntityDetailDrawer (KG 模式，对应 043)

### 视觉
- 右侧抽屉，宽 420 px，drawer 打开时画布右移 420 px（不覆盖）
- 顶部：type chip（color dot + 名称）+ entity 名（24 px semibold）+ alias 行（灰色，逗号分隔）
- 描述段：3 行 max + "Read more"
- **邻域统计条**：`5 TRIPLES · 1-HOP` + 折叠列表（5 条关系），格式：`relation_label · target_label`，点击 → 画布对应边 pulse + scroll center
- "Show all 8" 按钮展开剩余
- 大 CTA：`Ask about GraphRAG in Chat`（primary，全宽 44 px）
- 章节：
  1. **Evidence** · X chunks reference this entity（首条预览引文 + "Show all 47"）
  2. **Mentions trend**（mini ECharts sparkline，30 天 mention 数）
  3. **Co-occurring entities**（top 5 chips，点击 = 跳画布 focus）
  4. **Actions**：Cite in Chat / Hypothesize / Cross-paper reason / Add to watchlist / Pin in graph

### 状态
default / loading（每个 section skeleton）/ error（局部 retry）/ edge-mode（选中边时，顶部换 triple 表达，无 mentions sparkline）

### 交互
- Esc / 点击遮罩外不关闭（drawer 半模态，画布仍可交互）
- 顶部 X 按钮关闭，URL `?focus=` 清除
- 关系条目 hover：画布对应边 pulse；click：边 selected + drawer 切换到 edge-mode
- "Ask about ... in Chat" → composerStore.appendMention + 切到 S5 Chat
- Hypothesize → 调 `POST /api/v1/hypothesis` 用 entity 作种子
- Cross-paper reason → 跳 S7 Reasoning 预填该 entity
- Pin in graph → cy.node.lock()，重布局时不动

### A11y
- `role="dialog" aria-labelledby="entity-name"`
- Tab trap 内部，Esc 关闭
- 关系列表 `<ul role="list">`，每项可键盘聚焦
- mini chart 提供 `aria-label="Mentions over last 30 days, peak 12 on May 10"`

### 动效
- drawer 滑入 280 ms cubic-bezier(0.32, 0.72, 0, 1)
- 画布 transition margin-right 280 ms 同步
- 关系条目 hover 边 pulse：scale 1 → 1.06 → 1，2 次
- sparkline 数据进入 480 ms 描点

### Vue 实现
```ts
// EntityDetailDrawer.vue
const props = defineProps<{ entityId: string }>()
const { data: entity } = useEntity(props.entityId)        // SWR
const { data: triples } = useEntityTriples(props.entityId)
const { data: chunks } = useEntityChunks(props.entityId, { limit: 1 })

const hoverTripleId = ref<string | null>(null)
watch(hoverTripleId, (id) => kgCanvasBus.emit('pulse-edge', id))

function citeInChat() {
  composerStore.appendMention({ id: props.entityId, label: entity.value.label, type: entity.value.type })
  router.push(`/lib/${libId}/chat`)
}
```

### 联动
- KGCanvas ↔ Drawer：双向，selected 同步
- Drawer ↔ EvidencePanel：点 chunk → 跳 Evidence S6 并 highlight chunk
- Drawer ↔ Chat：cite 行为
- Drawer ↔ Reasoning：cross-paper 跳转预填

### UI 参数（来自 UI_PROMPTS §03-T）

| 类别 | 值 |
|---|---|
| Drawer 宽度 | 360（PROMPTS §03-T）；文档主体 420，本批切片任务要求 440 —— 三者冲突，**以 PROMPTS 为准 360**，文档主体 420 与 task 440 标注冲突 |
| 停靠 | 右侧；bg `bg-surface` #FFFFFF；左侧 1 `border-subtle` #E4E4E0；padding 24；gap 16 |
| Type pill | BaseBadge KG 变体 "● Concept" 76 × 26 radius pill |
| Entity 名 | h2 22/26.6 700（PROMPTS）；切片任务称"顶部 entity name 字号" = h2 22 |
| aka 行 | body-sm 13/15.7 400 `text-tertiary` #8C8C82，单行 truncate |
| Description | body 14/22 400 `text-secondary` #515151，max 4 行 |
| Section 标题 | meta 11/13.3 500 uppercase（如 "NEIGHBORHOOD · 9 triples · 1-hop"） |
| 关系列表行高 | 36 |
| 关系列表字体 | mono body-sm 13/20 400 |
| 关系列表 hover | bg `bg-subtle` #F4F4F1 |
| 关系列表展示 | 5 visible + "Show all N →" 链接 body-sm 600 brand-600 #3B30D9 |
| 关系分组 padding | — |
| 主 CTA | 312 × 44 primary "Ask about {entity} in Chat →" |
| Evidence 区 | meta 标题 + 1 条样例 italic body-sm `text-secondary`；包在 1 dashed box；底部 "Show all N →" body-sm 600 brand-600 #3B30D9 |
| 底部 actions 高度 | 44（与 primary CTA 同行高） |
| chunks 列表行高 | — |
| Type chip 样式 | dot 8 `<type>/500` + 名称 body-sm；bg `<type>/50` + text `<type>/700`；radius pill |

---

## 6. 性能与降级总策略

| 触发 | 行为 |
|---|---|
| nodes > 500 | 启用 batch render / textureOnViewport |
| nodes > 2k | 关 label 默认；fcose draft |
| nodes > 3k | **lazy import sigma.js**，切引擎；toast 告知 |
| nodes > 10k | 强制 community 聚类，仅渲染超节点 |
| FPS < 30 实测 | 自动降级一档 + 上报 telemetry |
| viewport change idle 200 ms | 触发 LOD：远景隐 label，近景出 label |
| memory > 600 MB | drop 历史 viewport snapshot |
| 后台 tab > 60 s | cy.stop() 暂停力导向 |

**reactivity 边界**：
- `engine` / `elements` / `selectedIds`（Set）/ `viewport` 全用 `shallowRef` / `ref<Set>`
- 不要把 Cytoscape Collection 塞进 reactive；用事件回调反推 Vue 状态
- 画布容器 `display: contents` 避免 layout thrash（父容器 grid 撑开）
- ResizeObserver 用 `requestAnimationFrame` 节流后调 `cy.resize()`

---

## 7. 导出 & 分享

| 方式 | 实现 |
|---|---|
| **PNG** | `cy.png({ scale: 2, full: true, bg: '#fff' })` → download |
| **SVG** | cytoscape-svg 插件，矢量保留 |
| **JSON** | `cy.json()` + 当前 filter，schema 显式版本号 |
| **分享链接** | base64url 编码 `{ filter, focus, depth, viewport, ts }` 进 `?state=`，打开自动还原（长度 > 1.5k 改 short-link 存后端） |
| **嵌入 iframe** | `/embed/kg/:libId?state=...`，无 chrome 版 |

---

## 8. URL 同步契约

`?focus=eid&depth=2&types=Concept,Method&relations=uses_method&conf=0.65&q=graphrag&zoom=1.2&px=300&py=-120`

- `useRouteQuery`（@vueuse/router）双向绑定
- 改 filter / focus 时使用 `router.replace`（不堆历史）
- 改 viewport 用 200 ms 防抖
- 后退/前进 → 还原 filter + focus + viewport

---

## 9. 与其他屏的联动一览

| 来源 | 动作 | 目标屏 |
|---|---|---|
| KGCanvas 右键 Cite | appendMention | S5 Chat composer |
| KGNode 单击 evidence link | 跳 chunk anchor | S6 Evidence |
| 多选 + Find paths | from=,to= | S7 Reasoning |
| FilterPanel preset | 写入 userPrefs | 全局（重开 KG 时还原） |
| Chat 中点 @entity | 高亮 + focus | S4 KG |
| Hypothesis output 节点 | inferred 边 + 入画布 | S4 KG（标 inferred） |

---

## 10. Vue Composition 草图（KGCanvas.vue）

```ts
// 仅展示 hook 与 ref 结构，不写全代码
import { ref, shallowRef, watch, watchEffect, onMounted, onBeforeUnmount } from 'vue'
import { watchDebounced, useResizeObserver } from '@vueuse/core'
import { useRouteQuery } from '@vueuse/router'
import type { IGraphEngine } from './KGCanvas.types'

const props = defineProps<{ libId: string }>()
const emit = defineEmits<{ select: [id: string]; ctxMenu: [...] }>()

// refs
const containerRef = ref<HTMLDivElement>()
const engine = shallowRef<IGraphEngine | null>(null)
const isLoading = ref(true)
const isDegraded = ref(false)
const hoveredId = ref<string | null>(null)

// URL ↔ state（单一事实源）
const focus = useRouteQuery('focus', '')
const depth = useRouteQuery('depth', 1, { transform: Number })
const filter = useKGFilter()                          // Pinia store
const viewport = useViewportSync()                    // 内部 useRouteQuery + debounce

// 数据
const { data, isFetching, error } = useNeighborhood({
  libId: () => props.libId, focus, depth, filter: filter.serialized,
})

// 引擎选择 + 切换
async function pickAdapter(nodeCount: number) {
  if (nodeCount > 3000) {
    isDegraded.value = true
    return (await import('./adapters/sigmaAdapter')).create
  }
  return (await import('./adapters/cytoscapeAdapter')).create
}

// 初始化
onMounted(async () => {
  const create = await pickAdapter(data.value?.nodes.length ?? 0)
  engine.value = create(containerRef.value!, {
    onNodeClick:  (id) => emit('select', id),
    onNodeHover:  (id) => { hoveredId.value = id },
    onCtxMenu:    (t, ty) => emit('ctxMenu', t, ty),
    onViewport:   (vp) => viewport.set(vp),
    onError:      (e) => kgErrorStore.push(e),
  })
  if (data.value) engine.value.setGraph(data.value)
})

// 数据变化 → setGraph
watch(data, (g) => g && engine.value?.setGraph(g))

// filter 变化（client 端） → 300 ms 防抖应用 class
watchDebounced(filter.serialized, (s) => engine.value?.applyClientFilter(s), { debounce: 300 })

// focus 变化 → 居中动画
watch(focus, (id) => id && engine.value?.focusNode(id, { animate: true }))

// hover → 1 度邻居高亮
watch(hoveredId, (id) => engine.value?.highlightNeighborhood(id))

// resize
useResizeObserver(containerRef, () => engine.value?.resize())

// 键盘
useKGKeyboard(engine, { fitKey: '0', exportKey: 'mod+e', shareKey: 'mod+l' })

// 销毁
onBeforeUnmount(() => engine.value?.destroy())
```

---

## 11. 三条铁律

1. **标签默认折叠**：zoom < 0.6 全隐，仅 hover/selected 显；密集图标签重叠是阅读体验的头号杀手。
2. **Hover 高亮"1 度邻居高亮 + 其余降透 30%"，不是全部变暗**：保留全局上下文，否则用户失去空间感（这是 Cytoscape 社区公认 best practice）。
3. **Filter 永远反映在 URL**：包括 types / relations / depth / confidence / focus / viewport；分享、刷新、后退都能还原；URL 是单一事实源，store 只是镜像。

---

## 附：颜色与形状映射（与 Cobalt Lab token 同步）

| Type | Color token | Shape | Hex（参考） |
|---|---|---|---|
| Concept | `--kg-cat-1` | ellipse | #6366F1 |
| Method | `--kg-cat-2` | hexagon | #10B981 |
| Dataset | `--kg-cat-3` | round-rectangle | #F59E0B |
| Metric | `--kg-cat-4` | triangle | #06B6D4 |
| Author | `--kg-cat-5` | ellipse + portrait | #8B5CF6 |
| Venue | `--kg-cat-6` | diamond | #EF4444 |
| …（共 12） | … | … | colorblind-safe |

---

## 12 色 colorblind-safe entity palette 速查表

> 来源：FRONTEND_DESIGN_SPEC.md §1.1（仅列出 6 个 KG entity 类型 token，未给出 12 色完整 palette）+ UI_PROMPTS §03-P/Q/R/S/T（同 6 色，权威 Hex）。
>
> **状态：SPEC 中 12 色 colorblind-safe palette 未定义**。当前权威只到 6 色（与 PROMPTS Hex 全对齐）；剩余 7–12 槽位待设计补全后回填。

| # | Type | Token | Hex（PROMPTS / SPEC 一致） | 形状 |
|---|---|---|---|---|
| 1 | Concept | `--kg-cat-1` | #4F46E4 (cobalt) | ellipse |
| 2 | Method | `--kg-cat-2` | #10B881 (emerald) | hexagon |
| 3 | Dataset | `--kg-cat-3` | #F59E0A (amber) | round-rectangle |
| 4 | Metric | `--kg-cat-4` | #06B6D3 (cyan) | triangle |
| 5 | Author | `--kg-cat-5` | #A854F7 (violet) | ellipse + portrait |
| 6 | Venue | `--kg-cat-6` | #EB4799 (pink) | diamond |
| 7 | — | `--kg-cat-7` | — | — |
| 8 | — | `--kg-cat-8` | — | — |
| 9 | — | `--kg-cat-9` | — | — |
| 10 | — | `--kg-cat-10` | — | — |
| 11 | — | `--kg-cat-11` | — | — |
| 12 | — | `--kg-cat-12` | — | — |

> 注：SPEC §1.1 Hex 与文档主体附表的"参考 Hex"（#6366F1 / #8B5CF6 / #EF4444 等）不一致 —— **以 PROMPTS = SPEC §1.1 一致值为准**：Concept #4F46E4、Method #10B881、Dataset #F59E0A、Metric #06B6D3、Author #A854F7、Venue #EB4799。
