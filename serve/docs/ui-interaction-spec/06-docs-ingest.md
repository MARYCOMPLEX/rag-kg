# 06 · 文献库 + 摄取流水线 + 长任务进度 交互规范

> 范围：S6 `/lib/:id/docs` 文献库 + 摄取 5 态流水线 + S5 综述生成等长任务（PipelineTree / RunStats / LiveCitation / DraftStreaming）
> 适用：RAG-KG Copilot 前端（Vue 3.4 + Pinia + Naive UI + UnoCSS + `@tanstack/vue-table`）
> 核心原则：**SHA-256 幂等** + **单 SSE 流多 subscriber** + **长任务可后台化（不阻塞导航）**

---

## §06.1 DropZone — 拖拽上传区（044）

### 视觉
图 044 展示 4 态：
- **default**：暖灰 2 px 虚线框（`border-default` + `dashed`），居中"上传云"图标 18 / 24，标题 16 sm-semibold "Drop PDFs, ZIPs, or folders here"，副标题 13 secondary "Files attach to graphrag-survey · parsing pipeline auto-routes to MinerU / Nougat"，最底行 12 tertiary "or click 'Upload PDFs' above · resumable, idempotent (SHA-256 dedup)"。圆角 `card`(14)。
- **hover / drag-over**：虚线变 `brand-500` 实色 1.5 px + 整框背景 `brand-100`（鸽紫淡底）+ 阴影 `focus`；图标轻微上移 4 px。
- **active-drop (file released)**：虚线短暂闪 `brand-600` 1 帧 → 立即变 indeterminate `n-spin` 包裹标题，文案改 "Hashing 3 files…"。
- **compact variant**：缩小成横向 72 px 卡片（位于 Documents 表格 sticky header 上方，已有文档时常驻），高度更小但保持同三态。

### 状态机
```
idle ──drag-over──> hover ──drop──> hashing ──> uploading ──> done|reject
   ↑                                                              │
   └──────────────────────────reset(2s)───────────────────────────┘
```

### 交互
1. **拖拽**：整个 dropzone 监听 `dragenter/over/leave/drop`。`dragenter` 计数器 +1，`dragleave` -1，归零才回 idle，规避子元素冒泡误触发。
2. **点击 fallback**：整个区域 `role="button" tabindex="0"`，Enter / Space 触发隐藏 `<input type="file" multiple accept="application/pdf,.zip">`。
3. **多文件 + 文件夹**：DataTransferItem.webkitGetAsEntry 递归读 ZIP / folder（参见 ADR-0019 zip-folder-upload-pipeline），单次最多 200 文件软上限，超出 toast warning "Only first 200 enqueued".
4. **类型校验**：先看 `file.type === 'application/pdf'`，**再用 `file-type` lib 读前 4 KB magic bytes** 防止伪造 mime；非 PDF / 非 ZIP → toast danger + 在 dropzone 右下贴 chip "1 rejected (not PDF)" 3 秒后淡出。
5. **SHA-256 幂等**：浏览器侧 `crypto.subtle.digest('SHA-256', buffer)` 计算（Web Worker，避免阻塞主线程）→ POST `/docs:check` 批量比对 → 命中已存在的，**不报错**，在表格中以 `Already in library` info 行 chip 显示 + dropzone 角标 "2 deduped"。
6. **大文件分片**：>50 MB 启用分片（5 MB / chunk，`multipart/form-data` + `Content-Range`），后端 `/docs:resumable` 协议（断点续传，断网回来 useEventSource 重连后从上次 offset 继续）；<50 MB 直接 `multipart` 单请求，避免无谓复杂度。

### A11y
- `aria-label="Upload PDF documents"`；
- 拖拽中 `aria-live="polite"` 播报 "3 files detected, release to upload"；
- 键盘用户：Tab focus → focus-ring (`focus` shadow token)，Enter 打开文件选择器。

### 动效
- drag-over 进入：`ease-out 120ms`（背景 + 边框同时过渡）；
- drop 时图标向上 4 px + 标题 fade out → spinner fade in 用 `<Transition mode="out-in">`；
- 拒收 toast 抖动 6 px → 0，单次 240 ms `spring`。

### Vue 实现
```vue
<!-- components/docs/DropZone.vue -->
<script setup lang="ts">
import { useDropZone } from '@vueuse/core'
import { fileTypeFromBlob } from 'file-type'
import { useIngestStore } from '@/stores/ingest'

const root = ref<HTMLElement>()
const ingest = useIngestStore()

const { isOverDropZone } = useDropZone(root, {
  onDrop: handle,
  dataTypes: ['application/pdf', 'application/zip'],
  multiple: true,
})

async function handle(files: File[] | null) {
  if (!files) return
  const accepted: File[] = []
  for (const f of files) {
    const t = await fileTypeFromBlob(f)
    if (t?.mime === 'application/pdf' || t?.mime === 'application/zip') accepted.push(f)
    else ingest.reject(f, 'not_pdf')
  }
  await ingest.enqueue(accepted) // 内部做 sha256 + /docs:check + upload
}
</script>
```

### 联动
- `ingestStore.enqueue()` → 每个文件创建 `IngestJob{ id, sha, status:'queued' }` → POST `/docs` 返回 `taskId` → store 注册到 `useTaskStream(taskId)` → Documents 表格行实时刷新。
- 完成后 toast success "3 documents indexed · 12 deduped"，点击跳到 `/lib/:id/docs?filter=just-uploaded`。

### 选型理由
- 不用 `vue-upload-component`：API 过于陈旧、样式难自定义；
- 自写 + `useDropZone` + 后端 `multipart` resumable：与 ADR-0019 ZIP/folder pipeline 对齐，且能复用 SSE 进度通道。

### UI 参数（来自 UI_PROMPTS §03-U）

| 类别 | 值 |
|---|---|
| 高度 | 120（full-width 标准）/ 380（empty-Documents 紧凑变体）/ 72（已有文档时 sticky compact，§06.1 文档约定，PROMPTS 未指定该变体高度） |
| 圆角 | 14（card） |
| 边框（idle） | dashed 1.5 border-default #D3D3CE（注：§06.1 文档原写 "2 px dashed border-default"，**以 PROMPTS 1.5 为准**） |
| 边框（drag-over） | dashed 2 brand-500 #4F46E4 + border-strong 语义 |
| 边框（active-drop） | brand-500 progress bar across the bottom 3h |
| idle 背景 | bg-canvas #FAFAF9（"slightly darker than surface to invite drop"） |
| drag-over 背景 | brand-50 #EDF0FF @ 30% opacity（注：§06.1 文档原写 `brand-100`，**以 PROMPTS brand-50@30% 为准**） |
| drag-over 变换 | scale(1.01) |
| 中心 icon | Lucide `upload-cloud` 32 stroke 1.5 text-tertiary #8C8C82（drag-over 时变 brand-500 #4F46E4；注：§06.1 文档原写 "18/24"，**以 PROMPTS 32 为准**） |
| 主标题 | body-lg 16/22 weight 600 text-primary #1A1A1A — "Drop PDFs, ZIPs, or folders here" |
| 副文案 | body-sm 13/15.7 text-secondary #515151 — "Files attach to graphrag-survey · parsing pipeline auto-routes to MinerU / Nougat" |
| 帮助文案 | caption 12/14.5 text-tertiary #8C8C82 — "or click 'Upload PDFs' above · resumable, idempotent (SHA-256 dedupe)" |
| 内容对齐 | 居中（垂直 + 水平） |
| 动效 | hover/focus 120ms ease-out（border-color + background-color + transform 同步）；drop 后图标 +4px translateY + spinner fade 用 `<Transition mode="out-in">`；拒收 toast 抖动 6→0 px 240ms spring |
| a11y focus ring | shadow `focus` = `0 0 0 3px rgba(79,70,229,.20)` |

---

## §06.2 Document Row + Table（045）

### 视觉
图 045 展示一张密度适中的表，列序：
| TITLE | YEAR | STATUS | CHUNKS | ENTITIES | INGESTED | ACTION |

- **行高** 64 px（双行：title + venue/authors meta）；
- **title** 14 base-semibold `text-primary`，**venue / authors** 12 `text-secondary`，省略号 `truncate`；
- **status pill** 用 §03 BadgePill：Ready (success-100/700) · Indexing (brand-100/700 + 内嵌 mini bar) · Parsing (warning-100/700 + spinner) · Failed (danger-100/700 + ⚠)；
- **chunks** 列 mono 数字，`Indexing` 行显示 `67 / 96` + 78 % 进度条；
- **entities** mono；
- **ingested** 相对时间 "2 days ago"，hover tooltip 显示绝对时间 + size；
- **action** 列 hover 时才显示三按钮（…/重摄取/删除），默认仅 `…`；
- **Failed 行展开 Popover**：错误码 `PARSING_FAILED` / Stage `PDF Parsing` / Detail "No text blocks found" + "Retry with MinerU" 按钮。
- 列头排序箭头 `↕ / ↑ / ↓` mono；
- 底部 "2,178 more docs" 居中 cta 加载更多（或自动虚拟化）。

### 状态
- row 状态映射 status pill；
- 多选：左侧 checkbox（hover 时显示，已选行 `brand-100` 底色 + 持久显示）；
- 多选后 sticky 顶部 actionbar "3 selected · Re-ingest · Delete · Export BibTeX · Clear"。

### 交互
1. **单击行** → 打开 DocumentDetailDrawer（§06.4）；
2. **单击 status pill** → 切到 `Activity` 抽屉锚到该文档；
3. **失败行** 单击触发 popover（而非抽屉），Retry 走 `/docs/:id:retry` mutation；
4. **排序**：title / year / chunks / ingested / status；
5. **筛选**（顶 ToolbarChips，§04）：status (multi) / source (mineru/nougat) / tag / year range；
6. **多选**：Shift+Click 区间选；Cmd/Ctrl+A 全选可见；按 ESC 清除选择；
7. **键盘**：↑↓ 导航，Enter 打开抽屉，Space 切换选中，Cmd+Delete 删除选中。

### A11y
- `<table role="grid">`，行 `role="row" aria-rowindex` + `aria-selected`；
- 排序列 `aria-sort="ascending|descending|none"`；
- status pill `aria-label="Status: Indexing 67 of 96 chunks, 70 percent"`；
- 失败行的 Retry 按钮放 popover 内但有 `aria-describedby` 指向行 id，让屏幕阅读器把"错误码 + Retry"绑成一组。

### 动效
- row hover：背景 `bg-subtle` 100 ms `ease-out`；
- 多选 actionbar：`slide-down` 140 ms `spring`；
- 状态从 `Indexing → Ready` 时 pill 闪一下 `brand-200` → `success-100` 320 ms（提示用户看见变化）；
- 失败 popover：`scale .96 → 1` + `fade` 160 ms。

### Vue 实现 — 表格库选型
**结论：用 `@tanstack/vue-table`（headless）**。理由：
| 维度 | TanStack Table | Naive `n-data-table` | 自写 |
|---|---|---|---|
| Headless | ✅ 完全 | ❌ 强绑 Naive 视觉 | ✅ |
| 列定义 type-safe | ✅ TS 第一公民 | △ Naive 类型偏弱 | ✅ |
| sort / filter / grouping / column visibility | ✅ 内置 | △ 部分内置 | ❌ 全要自写 |
| 虚拟化集成 | ✅ 与 `@tanstack/vue-virtual` 同源 | △ Naive 自带但耦合 | 自接 `vue-virtual-scroller` |
| 视觉自由度 | ✅ 完全用 UnoCSS token | ❌ 与 Cobalt Lab 不兼容 | ✅ |
| 学习成本 | 中 | 低 | 高 |

> Naive 已被业务"薄包装"原则限制为仅在 Modal / Drawer / Toast / Popover 用，表格这种长期演化的承载组件必须 headless，不能让第三方 UI 库决定我们的设计 token。

```ts
// composables/useDocumentsTable.ts
import { useVueTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel } from '@tanstack/vue-table'

export function useDocumentsTable(rows: Ref<DocRow[]>) {
  const columns: ColumnDef<DocRow>[] = [
    { id: 'select', size: 40, header: SelectAllCell, cell: SelectCell },
    { accessorKey: 'title', header: 'Title', cell: TitleCell, size: 360 },
    { accessorKey: 'year', header: 'Year', size: 64 },
    { accessorKey: 'status', header: 'Status', cell: StatusPillCell, size: 140,
      filterFn: (row, _id, val: string[]) => val.includes(row.original.status) },
    { accessorKey: 'chunks', header: 'Chunks', cell: ChunksProgressCell, size: 120 },
    { accessorKey: 'entities', header: 'Entities', size: 88 },
    { accessorKey: 'ingestedAt', header: 'Ingested', cell: RelativeTimeCell, size: 100 },
    { id: 'action', size: 56, cell: RowActionsCell },
  ]
  return useVueTable({
    data: rows.value, columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    enableRowSelection: true,
  })
}
```

虚拟化：行数 > 200 时启用 `vue-virtual-scroller` 的 `RecycleScroller`（item-size=64，buffer=400），rows 来自 store getter 已排序数组，避免每次重建。

### 联动
- store 同步：`ingestStore.jobs[].onProgress` → `documentsStore.updateRow(sha, { status, chunks })` → reactivity 推到表格；
- 行选择写到 `docsStore.selection: Set<string>`，AppBar 顶部 selected actionbar 也读这同一 Set；
- 与 Chat 联动：从 chat 的 citation badge 跳过来时 URL 带 `?doc=sha:xxxx` → table 自动 scrollIntoView + 行 `brand-200` 闪烁 600 ms。

### UI 参数（来自 UI_PROMPTS §03-V）

| 类别 | 值 |
|---|---|
| 表宽 | 1376 |
| 数据行高 | 64 |
| 行边框（底） | 1 border-subtle #E4E4E0 |
| 单元内边距 | 0 / 16（horizontal 16，无 vertical padding，由行高约束） |
| 列宽 — TITLE | flex-1（剩余空间，单行 truncate；title body 14/16.9 weight 600 text-primary #1A1A1A + 下方 meta caption 12/14.5 text-tertiary #8C8C82 "Edge et al. · Microsoft Research · arXiv:2404.16130"） |
| 列宽 — YEAR | 72（mono caption 12/14.5 text-secondary #515151，右对齐数字） |
| 列宽 — STATUS | 140（StatusPill + 在 in-progress 时下方内嵌 88×3 progress bar + mono caption "70%"；注：§06.2 文档写 size:140） |
| 列宽 — CHUNKS | 96（mono 14/22 text-primary #1A1A1A，右对齐；indexing 中显示 "— / 96"；注：§06.2 文档曾写 120） |
| 列宽 — ENTITIES | 96（mono 14/22；未完成时 "—"；注：§06.2 文档曾写 88） |
| 列宽 — INGESTED | 140（body-sm 13/15.7 text-tertiary #8C8C82；"3 days ago" / "just now · 32%"；注：§06.2 文档曾写 100） |
| 列宽 — ACTION | 40（kebab `⋯` icon button；注：§06.2 文档曾写 56） |
| 表头行高 | 48 |
| 表头背景 | bg-subtle #F4F4F1 |
| 表头文字 | meta uppercase 11/13.3 weight 500 text-tertiary #8C8C82，含 sortable indicators |
| Status pill 五态 | Ready = success-50 #EBFCF5 / success-700 #047856 + `●`；Indexing = brand-50 #EDF0FF / brand-700 #2A1FAF + `◐`；Parsing = brand-50 #EDF0FF / brand-700 #2A1FAF + `◐`（PROMPTS 把 Indexing/Parsing 都置于 brand）；Failed = danger-50 #FDF1F1 / danger-700 #B91B1B + `⊘`；Queued = bg-muted #EAEAE5 / text-secondary #515151（PROMPTS 未单独画 Queued，沿用 §03 BadgePill） |
| hover 背景 | bg-subtle #F4F4F1 100ms ease-out |
| 选中态背景 | brand-100 #DCE2FF（多选行；注：§06.2 文档约定） |
| 失败行 action | "↻ Retry with MinerU" small ghost link 放在 action 区，pill 单击触发 FailedErrorPopover（03-AQ） |
| 表尾摘要行 | "… 2,179 more docs" caption 12/14.5 text-tertiary #8C8C82，居中 |
| 行 hover action 显隐 | hover 才显示三按钮（…/重摄取/删除），默认仅 `…` |
| 动效 | 状态 Indexing→Ready 时 pill 闪 brand-200 #B2BCF4 → success-100 320ms |

---

## §06.3 IngestStepper — 每文档摄取进度（046）

### 视觉
图 046 显示两种条：**Determinate (70 %)** 与 **Indeterminate**。
- 顶部矩形 chip：`Parsing` 字样 + 左侧 brand-spinner 旋转图标（半月）；chip 自身有 1 px 内边线和淡 `brand-100` 描边；
- chip 下面一条 6 px 高 brand 进度条；
- 底部行："2m ago · 70 %"（确定）或 "2m ago · —"（不确定）。

### 5 段步骤映射（实际 5 态）
```
queued → parsing → chunking → embedding → indexing → done
                                                 └─→ failed
```
- **parsing**：MinerU / Nougat（不可估算分母 → indeterminate bar + 动态 stripe）；
- **chunking**：可估算（按 page 切片） → determinate；
- **embedding**：分母明确（`embedded / total chunks`） → determinate + 文案 `embedding 234 / 512 chunks`；
- **indexing**：FAISS + Neo4j 双写，三段，分别 mini bar；
- **done**：chip 替换为 `Ready` success pill，3 秒后整个 stepper 折叠成 1 行 ready 摘要；
- **failed**：chip 替换为 `Failed` danger pill + 点击 → FailedErrorPopover（含错误码 / stage / detail / Retry 按钮）。

### 交互
- chip 单击 → 展开 `n-popover`，显示 5 段 mini-stepper（`n-steps` 包装），每段：状态点 / 耗时 / 当前文案；
- 失败段红色 ×，行内 Retry 按钮触发 `/docs/:id:retry` POST；
- 任何状态切换都从 `useTaskStream(taskId)` 取得（不轮询）。

### A11y
- `role="progressbar" aria-valuenow aria-valuemin=0 aria-valuemax=100` （indeterminate 时省略 valuenow + `aria-valuetext="processing"`）；
- chip 文案改变时 `aria-live="polite"`。

### 动效
- 状态跃迁：chip 旋转图标做 `rotate-y 180°` 翻面 240 ms，颜色 cross-fade；
- 进度条数字 mono tabular-nums，避免抖动；
- indeterminate 用 CSS keyframe `bar-slide` 1.2 s linear infinite（不可省 reduced-motion 兜底：检测 `prefers-reduced-motion` 改成静止 50 % 灰条 + 文字 `working`）。

### Vue 实现
```vue
<!-- components/docs/IngestStepper.vue -->
<script setup lang="ts">
const props = defineProps<{ jobId: string }>()
const { state } = useTaskStream(props.jobId)
const pct = computed(() => state.value.totals?.percent ?? null)
const stage = computed(() => state.value.stage)
const failed = computed(() => state.value.status === 'failed')
</script>
<template>
  <div class="rounded-card border border-default p-3 bg-surface">
    <div class="flex items-center gap-2">
      <StageIcon :stage="stage" :failed="failed" />
      <span class="font-medium">{{ STAGE_LABEL[stage] }}</span>
    </div>
    <ProgressBar :value="pct" :indeterminate="pct === null" :failed="failed" class="mt-2" />
    <div class="text-12 text-secondary mt-1 font-mono">
      {{ relTime(state.startedAt) }} · {{ pct == null ? '—' : `${pct}%` }}
    </div>
  </div>
</template>
```

### 联动
- 同一 jobId 同时被 Table StatusPillCell 和 Drawer 内 Stepper 订阅 → useTaskStream 内部 ref-count，只开一个 EventSource。

### UI 参数（来自 UI_PROMPTS §03-W）

| 类别 | 值 |
|---|---|
| 整体尺寸 | 88w × 22h pill（行内变体，用于 Documents 表格 Status 列下） |
| pill 文字 | mono-sm weight 600 — 如 "◐ Parsing"（leading StatusPill） |
| 进度条尺寸 | 88w × 3h（位于 pill 下方） |
| 进度条圆角 | 999（pill 圆角） |
| 进度条填充 | brand-500 #4F46E4 至 value%；track bg-muted #EAEAE5 |
| 副文案 | body-sm 13/15.7 text-tertiary #8C8C82 — 如 "2m ago · 70%" |
| 5 段步骤色 | queued = bg-muted #EAEAE5 / text-secondary #515151（PROMPTS 未单独列色，按 §06.3 文档约定）；parsing = brand-50 #EDF0FF / brand-700 #2A1FAF（PROMPTS Status pill `Parsing` 用 brand）；chunking = brand-50 #EDF0FF / brand-700 #2A1FAF（PROMPTS 未单独列，与 parsing 同族）；embedding = brand-50 #EDF0FF / brand-700 #2A1FAF（同上）；indexing = brand-50 #EDF0FF / brand-700 #2A1FAF（PROMPTS `Indexing` pill 用 brand）；done = success-50 #EBFCF5 / success-700 #047856 `● Ready`；failed = danger-50 #FDF1F1 / danger-700 #B91B1B `⊘ Failed` |
| indeterminate 动画 | 30%-wide brand-500 #4F46E4 段从左→右 1.4s 循环（CSS keyframe `bar-slide`） |
| 当前步骤动画 | chip 上半月 spinner 图标持续旋转；状态跃迁时 chip 做 `rotate-y 180°` 翻面 240ms + 颜色 cross-fade |
| 失败 × 尺寸 | StatusPill `⊘ Failed` 内 icon 与 pill 文字同字号（mono-sm 600）；详细 ✗ 子段用 success/danger 圆点 20×20（与 §03-Y 共用） |
| 重试按钮 | 行内 small ghost link "↻ Retry with MinerU"，文字 body-sm 13/15.7 brand-600 #3B30D9（参见 §03-V Action 列） |
| reduced-motion | 检测 `prefers-reduced-motion` → indeterminate 改静止 50% 灰条 #EAEAE5 + 文字 "working" |
| 数字字体 | mono tabular-nums（避免抖动） |

---

## §06.4 DocumentDetailDrawer — 文档详情抽屉（047）

### 视觉
右侧抽屉宽 720 px（移动端全屏），头部 PDF icon + 标题 "Graph Neural Networks for Molecules: A Survey" + 右上 `Open in tab` icon + `×`。

- **meta line**：来源 chip (arxiv) · `PDF` · `3.7 MB` · `Ingested 2024-05-12 14:32`；
- **4-up KPI 卡**：chunks 128 / entities 94 / triples 218 / pages 22（mono 28 数字 + 12 tertiary 标签）；
- **左下 PDF preview**：占位 thumbnail，下方分页 "page 1 of 22"；
- **右下 Sections 列表**：1 Abstract / 2 Introduction / …（带数字索引列，单击跳到 chunk）；
- **Key chunks** 列表（左下，下方）：`chunk_2873 §4.5 · p.4 · "…we observe that local search is appropriate…"` mono chunk_id；
- **底部行动条** sticky：`Re-parse`（左）/ **Open in Chat / Ask**（主蓝按钮）/ `Remove document`（右 danger ghost）。

### 状态
- 抽屉打开方式：表格行点击 / Chat citation 点击 / 命令面板 `Go to doc xxx`；
- KPI 数为 0 时显示 `—`，不显示 0；
- PDF preview 加载中：skeleton 灰块 + spinner；加载失败：占位 + Retry。

### 交互
- 单击 chunk → 高亮其在 PDF preview 中的页（PDF.js 渲染时 `highlight` overlay）+ scroll 到对应位置；
- `Open in Chat` → 关抽屉 → 新 chat 自动塞入 system context "doc:{sha}" prefix；
- `Remove document` → confirm modal（输入 doc title 二次确认）→ DELETE `/docs/:id`，Toast undo 5 秒（软删 5 秒后硬删）；
- `Re-parse` → 重新进 queued 态，stepper 重启。

### A11y
- `role="dialog" aria-modal="true" aria-labelledby="drawer-title"`；
- ESC 关闭；focus trap 进入抽屉，关闭后归还 focus 到触发行；
- Sections 列表是 `role="list"`，每项 `<button>` 可键盘 ↑↓ 浏览。

### 动效
- 抽屉滑入：`translateX 100 % → 0` 200 ms `ease-out`；
- KPI 数字 mount 时 count-up 360 ms（`@vueuse/core` useTransition）。

### Vue 实现
```vue
<NDrawer v-model:show="open" :width="720" placement="right">
  <NDrawerContent :closable="true" :title="doc.title">
    <DocMetaLine :doc="doc" />
    <DocKpiGrid :doc="doc" />
    <div class="grid grid-cols-[1fr_1fr] gap-4 mt-4">
      <PdfPreviewPane :sha="doc.sha" v-model:page="page" />
      <SectionList :sections="doc.sections" @jump="jumpToChunk" />
    </div>
    <KeyChunksList :chunks="doc.keyChunks" @select="onChunk" class="mt-4" />
    <template #footer>
      <DrawerFooterActions :doc="doc" @reparse @open-chat @remove />
    </template>
  </NDrawerContent>
</NDrawer>
```

### 联动
- 抽屉内 chunk 单击 → emit('open-chunk', chunkId) → 全局 `evidenceStore.preview(chunkId)` → 触发 EvidenceCard preview popover；
- 与 Chat 同步：从 chat 跳来时携带 `?chunk=chunk_2873` 自动滚到该 chunk + 闪烁 brand-200 800 ms。

### UI 参数（来自 UI_PROMPTS §03-X）

| 类别 | 值 |
|---|---|
| 抽屉宽 × 高 | **800 × 900**（PROMPTS）；注：§06.4 文档原写 `width=720`，**以 PROMPTS 800 为准**；与 EvidencePanel 不同（EvidencePanel 在 §04 规范，此抽屉更宽） |
| 圆角 | 14（card；遵循 §03 全局 modal/big-panel=20 但 PROMPTS 子组件未单独写，此抽屉按 sub-widget 保持 14） |
| Stat group | 4 cell 横向一行，每 cell 80w |
| Stat 数字 | h2 22/26.6 weight 700 text-primary #1A1A1A，tabular-nums |
| Stat 标签 | caption 12/14.5 text-tertiary #8C8C82（"128 chunks" / "94 entities" / "218 triples" / "22 pages"） |
| PDF preview 区 | 336w × 408h placeholder card |
| PDF preview 背景 | bg-subtle #F4F4F1 |
| PDF preview 边框 | 1 border-subtle #E4E4E0 |
| PDF preview 圆角 | 14 |
| PDF preview 中心 icon | Lucide `file-text` 32 text-tertiary #8C8C82 |
| PDF preview 副标 | mono caption "📄 page 1 of 22" + label "PDF preview" |
| SectionsList 行高 | 36 |
| SectionsList 字体 | mono caption 12/14.5 text-secondary #515151（行内 "1   Abstract" 缩进格式） |
| SectionsList 缩进 | TOC 数字索引列前缀（mono），章节标题随其后，hover 背景 bg-subtle #F4F4F1 |
| SectionsList 行数（示例） | 12 |
| ChunksList 项形式 | 4px 左侧 brand-100 #DCE2FF accent rail |
| ChunksList 内容 | body-sm 13/15.7，mono `chunk_2871` 前缀 + `§4.5 · p.4 · "…we observe that local search is appropriate…"`（italic snippet） |
| Footer 按钮 gap | 8 |
| Footer — Secondary | "↻ Re-parse" 152w × 40h |
| Footer — Primary | "Open in Chat / Ask →" 200w × 40h（brand-500 #4F46E4） |
| Footer — Danger ghost | "Remove document" 152w × 40h |
| 抽屉滑入动画 | `translateX 100% → 0` 200ms ease-out |
| KPI count-up | 360ms（@vueuse/core useTransition） |

---

## §06.5 PipelineTree — 长任务进度树（048）

### 视觉
图 048 展示综述生成 7 段 pipeline 的展开树：
```
✅ Ingest                   1,248 docs · 326,771 chunks · Done
✅ Build Knowledge Graph    3,742 ent · 8,901 rel · Done
✅ Retrieve                 128 chunks · top-k 18 · Done
🔵 Rerank   ────────── 62 %  88 / 142 reranked · Running
   └── Model: bge-reranker-large · Batch: 16
       Score range: 0.15 → 0.98
○ Reason                   Pending
○ Draft                    Pending
○ Review                   Pending
```
- 节点左侧圆点状态色：成功 success / 进行 brand 脉冲 / 待办 灰空心 / 失败 danger ×；
- 节点行右侧 mono 统计：`<count> docs · <chunks> · <Done|62%|Pending>`；
- 当前节点展开显示子日志卡（淡 brand-50 底）；
- 顶部 `Pipeline` 标题 + `step 4 of 7 · 04:18 elapsed · ~03:30 ETA` + 右上 `Running` chip + `Run in bg ↗`；
- 底部 `RUN STATS` 6 行 KPI + 底部红色 `Cancel run` + 主蓝 `Download draft .md`。

### 状态
- 树节点状态：`pending` / `running` / `done` / `failed` / `skipped`（皆有 chip）；
- 当前活动节点 1 个 + 脉冲；同时只允许 1 个 running（pipeline 串行模型，参见 ADR-0009）；
- 失败节点固定展开 + 显示 stack trace tail（折叠 200 行）+ Retry from here 按钮。

### 交互
- 节点单击 → 展开 / 折叠子日志；
- 节点 hover 显示 mono cost / token 数 tooltip；
- 顶部 `Run in bg` → 任务转入后台（右下角悬浮 mini progress 出现），整树本身关闭但 store 继续订阅；
- `Cancel run` → confirm modal，DELETE `/tasks/:id`，整树灰化 + chip 变 `Cancelled`；
- `Download draft .md` → 取当前生成内容（即便未完成）。

### A11y
- `<ul role="tree">` + 子 `role="treeitem" aria-expanded aria-level`；
- 当前 running 节点 `aria-current="step"`；
- 脉冲动画 `prefers-reduced-motion` 退化为不闪烁仅蓝色边框。

### 动效
- 脉冲：`box-shadow` 在 `0 0 0 0 brand-400/40 → 0 0 0 10px transparent` 1.6 s ease-out infinite；
- 节点完成：`✓` 用 SVG path `stroke-dasharray` 描边动画 280 ms `spring`；
- 子节点展开：`max-height + fade` 200 ms。

### Vue 实现
```vue
<!-- components/tasks/PipelineTree.vue -->
<script setup lang="ts">
const props = defineProps<{ taskId: string }>()
const { tree, stats, status } = useTaskStream(props.taskId)
</script>
<template>
  <ul role="tree" class="space-y-1">
    <PipelineNode v-for="n in tree" :key="n.id" :node="n" />
  </ul>
  <RunStatsSidebar :stats="stats" :status="status" />
</template>
```

> 不用 `n-tree`：n-tree 强假设静态数据，我们要 SSE 流式追加 + 节点状态高频更新 + 自定义脉冲。自写 + 简单递归组件更轻。

### 联动
- `useTaskStream(taskId)` 暴露 `tree / stats / draft / citations` 4 个响应式视图 → PipelineTree / RunStats / Draft / LiveCitations 共用同一 EventSource。

### UI 参数（来自 UI_PROMPTS §03-Y）

| 类别 | 值 |
|---|---|
| 组件宽 | 280–320（容器宽度区间，常与 RunStats 同列） |
| 节点行高 | 56 |
| 左侧连接 rail | 垂直 2px brand-200 #B2BCF4（连接同级 sibling） |
| 状态圆点 icon | 20 × 20；done = filled `◉` brand-500 #4F46E4；active = spinning `◔` brand-500 #4F46E4；pending = hollow `◯` text-tertiary #8C8C82；failed = `✗` danger-500 #EE4444 |
| 节点标题 | body-sm 13/15.7 weight 600 text-primary #1A1A1A |
| 节点 meta（右对齐） | caption 12/14.5 text-tertiary #8C8C82 — 例 "412 tok · 3.2s"，mono tabular-nums |
| 子节点缩进 | +20 px（同图标方案） |
| 折叠箭头 | —（PROMPTS 未单独画折叠箭头；§06.5 文档约定 chevron 单击展开/折叠子日志） |
| 活动节点底色 | brand-50 #EDF0FF wash 铺整行 |
| 当前活动节点脉冲 | `box-shadow` `0 0 0 0 rgba(79,70,229,.40) → 0 0 0 10px transparent` 1.6s ease-out infinite |
| 流式叶子 | mono "writing…" + 22ms blink cursor |
| 耗时字号 | caption 12/14.5 mono tabular-nums text-tertiary #8C8C82 |
| 树下分隔线 | 1 border-subtle #E4E4E0 divider |
| RUN STATS label | meta 11/13.3 uppercase weight 500 text-tertiary #8C8C82 |
| RUN STATS 列表 | 2-column；mono numerals（"Tokens used 14,328 / 32,000" / "Cost so far $0.36" / "Elapsed 04:18" / "ETA ~03:30"） |
| 节点完成动画 | `✓` SVG `stroke-dasharray` 描边 280ms spring |
| 子节点展开 | `max-height + fade` 200ms |
| reduced-motion | 脉冲退化为不闪烁仅蓝色 1px brand-500 border |

---

## §06.6 RunStatsSidebar — 长任务统计侧栏（049）

### 视觉
PipelineTree 同屏右侧或底部，6 行 KPI（小屏自动横向滚）：
| INDEXED DOCS | CHUNKS | KG ENTITIES | RETRIEVED (RPS) | TOKENS (IN/OUT) | TOTAL COST (USD) | CONTEXT WINDOW | ERRORS |
| 1,248 | 326,771 | 3,742 | 128 / 128 chunks · 0.67 | 48,321 | $0.038 | 61 % used | 0 |

底部右侧 cta 组：`Cancel run`（danger ghost）/ `Download draft .md`（primary）。

### 进度环（可选展开模式）
- 中心环：cost used / budget（带数字中心 mono）；
- 环色：< 60 % brand / 60–85 % warning / > 85 % danger；
- 用纯 SVG（避免 ECharts 200 KB），或 `n-progress type="circle"`（轻量 wrap）。

### 状态
- 实时 `useTaskStream(taskId)` 推 stats 增量；
- `state stats update every 5s`（图底 hint，避免过快闪烁）：UI 节流 5 s commit 一次到 store，但 SSE 仍是事件驱动。

### 交互
- 单 KPI hover → tooltip 显示来源（"chunks retrieved by Hybrid Dense + KG"）；
- 单击 `View full logs` → 抽屉显示完整任务 audit log；
- `Cancel run` → 二次 confirm；
- "Run in bg" 后此组件迁移到右下悬浮 mini bubble（48 × 48 圆 + 进度环 + 点击展开恢复）。

### A11y
- KPI 数字 `aria-label="Tokens used 48,321 out of 32,000 budget"`；
- 取消按钮 `aria-describedby` 指向当前 task summary。

### 动效
- 数字 count-up 320 ms `ease-out`；
- 环增长 `stroke-dashoffset` 过渡 600 ms；
- 进入预算告警阈值时环色切换有 240 ms `cross-fade` + 一次 `pulse`。

### Vue 实现
```vue
<RunStatsSidebar>
  <StatGroup :rows="stats.rows" />
  <CostGauge :used="stats.costUsd" :budget="stats.budgetUsd" />
  <StatsFooter @cancel @download />
</RunStatsSidebar>
```

### 联动
- 当 `task.status === 'done'` → "Cancel run" 按钮淡出，替换为 "View report"；
- 当 `cost > budget * 0.85` → 全局 toast warning + 高亮 cost 行。

### UI 参数（来自 UI_PROMPTS §03-Z）

| 类别 | 值 |
|---|---|
| 面板宽 × 高 | 320 × 784 |
| 圆角 | 14 |
| 背景 | bg-surface #FFFFFF |
| 边框 | 1 border-subtle #E4E4E0 |
| 内边距 | 20 |
| Header 标题 | "Pipeline" h3 20/24.2 weight 600 text-primary #1A1A1A |
| Header 副标 | body-sm 13/15.7 text-tertiary #8C8C82 — "step 4 of 7 · 04:18 elapsed · ~03:30 left" |
| Header 状态 pill | "● Running" StatusPill 88w × 32h（top-right） |
| Header bg link | "Run in bg ↗" body-sm 13/15.7 weight 600 brand-600 #3B30D9（紧邻 Status pill） |
| Body | PipelineTree (03-Y) + RUN STATS block |
| 各指标卡间距 | —（PROMPTS 未单独写卡间距；§06.6 文档约定按 8/12/16 spacing token） |
| 进度环尺寸 | —（PROMPTS 未单独写进度环；§06.6 文档约定纯 SVG 或 `n-progress type="circle"` 轻量 wrap） |
| 数字字号 | mono 13/20（PROMPTS Typography Scale）；KPI 大数若需 h2 22/26.6 weight 700 tabular-nums（参 §03-X Stat 群） |
| Footer 布局 | sticky bottom；两按钮 50/50 |
| Footer — Cancel | "Cancel run" 130w × 40h danger-ghost |
| Footer — Download | "↓ Download draft .md" 142w × 40h secondary |
| 数字 count-up | 320ms ease-out |
| 环增长动画 | `stroke-dashoffset` 过渡 600ms |
| 预算告警切换 | 240ms cross-fade + 一次 pulse |

---

## §06.7 LiveCitationList — 实时引用列表（050）

### 视觉
图 050 显示一张窄列表（约 280 px 宽）：
- 顶部 `Live citations` 14 semibold + `29 unique sources · 0 broken · cross-checked` 12 secondary；
- 列表项左侧 mono 序号（1 / 2 / 3 …），右侧 1 行标题 + 1 行 authors+year 12 secondary；
- 第 2 行（GraphRAG）淡 brand-100 底色 → 表示 pinned；
- 末尾 `+ 22 more ↑` ghost 按钮（更多）。

### 状态
- 每条 citation 状态：`new` (刚到达，闪 200 ms brand-200) / `cited` (已被 draft 引用 → 加角标 §2.1 跳转锚) / `broken` (DOI 死链 → 红下划线)；
- pinned：top-10 自动锁定区，不被新到 citation 挤出。

### 交互
- 单击 citation → 打开 EvidenceCard preview popover（chunk + provenance + open in doc）；
- pin 按钮（hover 显示）→ 加入 top-10 区；
- 排序切换：discovery order（默认） / by score / by year；
- 滚动到底部 lazy load 更多。

### A11y
- `<ol role="list">`；
- 每项 `<button>` 包裹，回车打开 preview；
- pinned 区 `aria-label="Pinned top citations"`，单独 region landmark。

### 动效
- 新到达 citation：从顶部 slide-in（`translateY -8 → 0` + fade）200 ms；
- pin 切换：`scale .9 → 1` 弹一下；
- broken：红下划线渐显，附带 `⚠` 图标。

### Vue 实现
```ts
const { citations } = useTaskStream(props.taskId)
const pinned = computed(() => citations.value.filter(c => c.pinned).slice(0, 10))
const rest = computed(() => citations.value.filter(c => !c.pinned))
```

### 联动
- 与 §06.8 Draft 中的内联 `[1]` 角标双向跳转（鼠标 hover 角标 → list 对应行高亮 brand-100 + scroll）；
- 与 Chat 复用同一 EvidenceCard 组件（§04），保持 evidence 全局一致体验。

### UI 参数（来自 UI_PROMPTS §03-AA）

| 类别 | 值 |
|---|---|
| 面板宽 × 高 | 336 × 784（注：§06.7 文档曾写 "约 280 px 宽"，**以 PROMPTS 336 为准**） |
| 圆角 | 14 |
| 背景 | bg-surface #FFFFFF |
| 边框 | 1 border-subtle #E4E4E0 |
| 内边距 | 20 |
| Header 标题 | "Live citations" h3 20/24.2 weight 600 text-primary #1A1A1A |
| Header 副标 | caption 12/14.5 text-tertiary #8C8C82 — "29 unique sources · 0 broken · cross-checked" |
| 每条 chip 高度 | 64h（行高） |
| 每条 chip 内容 | CitationChip 26w × 20h + 标题 body-sm 13/15.7 weight 600 text-primary truncate 2 行 + meta caption 12/14.5 text-tertiary "Edge et al. 2024" |
| CitationChip 色 | info/citation-500 #06B6D3（cyan，PROMPTS 全局规则：CitationChip 用 info cyan 而非 brand indigo） |
| hover 背景 | bg-subtle #F4F4F1 |
| pinned 区分隔线 | —（PROMPTS 未画显式分隔线；§06.7 文档约定 pinned 行 brand-100 #DCE2FF 底色 + region landmark 区隔） |
| 排序切换按钮 | —（PROMPTS 未画切换按钮；§06.7 文档约定 discovery / by score / by year，按 §03 ToolbarChip 体系） |
| Footer 链接 | "+ 22 more →" body-sm 13/15.7 weight 600 brand-600 #3B30D9 |
| 新到达高亮 | bg brand-50 #EDF0FF 持续 800ms 后回常态 |
| 新到达 slide-in | `translateY -8 → 0` + fade 200ms |
| pin 切换 | `scale .9 → 1` 弹性 |

---

## §06.8 ReviewDraftStreamingView — 综述草稿流式视图（051）

### 视觉
图 051：左主区是一篇文章流式渲染：
- 顶部 `GraphRAG advances 2024–2025` display 28 + 副标题 `Draft · 524 / 3,000 words · 29 citations · graphrag-survey` mono 12 secondary；
- 章节标题 `1. Pre-trained models for KG construction` 22 semibold；
- 段落正文 16 base，行高 1.7；
- 内联 citation 角标 `[1]` `[8]` `[9]` 用 info-cyan chip （§03 CitationChip）；
- 段末文字带流式光标（22 ms 闪烁）；
- 章节下方 `Drafting subtopic 2 · Haiku 4.5 · 324 / 800 tokens` mono 12 secondary；
- 底部 chip 列表 `3. Community summaries · pending` `4. Eval & limitations · pending`；
- 黄色警示行 `⚠ No chunks matched this subtopic. Try widening your filter or upload more papers.`（章节级 warning）。

### 状态
- 章节级状态：`pending` / `drafting` / `done` / `warn-no-evidence` / `failed`；
- token 流式：复用 §04 chat `useTokenStream`；
- 章节完成后自动折叠（`>` 三角，可手动展开）；
- 右侧 minimap（70 px 宽 sticky）显示所有章节缩略 + 当前位置（IntersectionObserver 高亮）。

### 交互
- 当前流式段落自动 scroll 到视窗中部（用 `scrollIntoView({ block: 'center', behavior: 'smooth' })`，每 800 ms 节流，避免反复滚动晕眩）；
- 已完成章节双击标题折叠 / 展开；
- 章节末尾 actions：`Stop` (停止本章) / `Regenerate this section` / `Branch from here`（创建新草稿分支）；
- 内联 `[n]` 单击 → 打开 EvidenceCard，同时高亮 LiveCitationList 第 n 行；
- 右侧 minimap 单击章节 → 跳转。

### A11y
- 每章节 `<section aria-labelledby="sec-N">`；
- 流式区 `aria-live="polite" aria-busy="true"`，完成时 `aria-busy="false"`；
- citation 角标 `aria-label="Citation 1: Lewis et al 2020"`，可键盘 Tab 到。

### 动效
- token 接续：mono caret `|` 22 ms 闪烁（与 chat 同 token）；
- 章节完成：标题左侧 `✓` 出现 280 ms spring；
- 折叠：`max-height + fade` 200 ms；
- 自动 scroll：smooth 800 ms。

### Vue 实现
```vue
<!-- components/tasks/ReviewDraftStreamingView.vue -->
<script setup lang="ts">
const { draft, citations } = useTaskStream(props.taskId)
const activeSection = ref<string>()
useIntersectionObserver(sectionRefs, (entries) => {
  activeSection.value = entries.find(e => e.isIntersecting)?.target.id
})

function onTokenAppend() {
  // 节流的 center scroll
  scrollToCenterThrottled(currentParagraphRef.value)
}
</script>
```

> minimap 自写 70 px 列即可；不引 `vue-virtual-scroller`，章节数通常 < 30，不值得虚拟化。

### 联动
- 与 PipelineTree 的 `Draft` 节点状态同步：节点 `running` 时 draft 区出现 caret；节点 `done` 时整章节定型；
- 与 LiveCitationList 双向跳转；
- 草稿支持中途 `Run in bg` → 整页关闭但 store 继续接收 SSE → 完成时全局 toast "Draft ready · 3,012 words"。

### UI 参数（来自 UI_PROMPTS §03-AB）

| 类别 | 值 |
|---|---|
| 主区宽 × 高 | 688 × 784 |
| 圆角 | 14 |
| 背景 | bg-surface #FFFFFF |
| 边框 | 1 border-subtle #E4E4E0 |
| 内边距 | 32 |
| 区块间 gap | 16 |
| 文章主标题 h1 | display 36/43.6 weight 700 text-primary #1A1A1A — "GraphRAG advances 2024–2025"（注：§06.8 文档原写 "display 28"，**以 PROMPTS display 36 为准**） |
| Meta 行 | body-sm 13/15.7 text-tertiary #8C8C82 — "Draft · 524 / 3,000 words · 29 citations · graphrag-survey" |
| 主标题下分隔线 | 1 border-subtle #E4E4E0 |
| 章节标题 h2 | h2 22/26.6 weight 700 text-primary #1A1A1A — "1. Pre-trained models for KG construction" |
| 正文段落 | body 14/22 text-primary #1A1A1A（注：§06.8 文档原写 "16 base 行高 1.7"，**以 PROMPTS body 14/22 为准**） |
| 内联 CitationChip | info-cyan（§03 全局规则；尺寸 26 × 20 同 §03-AA） |
| 流式 caret | 2w × 16h brand-500 #4F46E4，22ms 闪烁、1.0Hz blink |
| 当前章节状态行 | meta caption 12/14.5 text-tertiary #8C8C82 — "Drafting subtopic 2 · Haiku 4.5 · 324 / 800 tokens" |
| 章节末分隔线 | 1 border-subtle #E4E4E0 |
| pending-section 预览 | body-sm 13/15.7 italic text-tertiary #8C8C82 — "3. Community summaries  ⏵ pending\n4. Eval & limitations  ⏵ pending" |
| 0-chunk 警告框 | inline box bg warning-50 #FFFAEB / text warning-700 #B45208 / body-sm 13/15.7 — "No chunks matched this subtopic. Try widening year filter or upload more papers." |
| 右侧 minimap 宽 | 70（§06.8 文档约定，PROMPTS 未单独画 minimap） |
| 已完成章节折叠 indicator | `>` 三角（§06.8 文档约定，PROMPTS 未单独画；折叠 `max-height + fade` 200ms） |
| 章节完成 ✓ | 标题左侧出现，spring 280ms |
| 自动 scroll-to-center | smooth 800ms，节流 800ms 避免反复滚动 |

---

## §06.Y 摄取 5 态颜色表

PROMPTS 把 Indexing/Parsing/Chunking/Embedding 共用 brand 系色，Done 用 success，Failed 用 danger，Queued 沿用中性灰。统一映射：

| 阶段 | StatusPill 文案 | icon | 背景 token / HEX | 文字 token / HEX | 进度条 fill | 出处 |
|---|---|---|---|---|---|---|
| queued | `· Queued` | `◯` | bg-muted #EAEAE5 | text-secondary #515151 | — (静止 50% 灰 #EAEAE5) | §03-V 沿用 §03 BadgePill（PROMPTS 未单独画 Queued） |
| parsing | `◐ Parsing` | half-moon spinner | brand-50 #EDF0FF | brand-700 #2A1FAF | brand-500 #4F46E4 indeterminate（30% segment 1.4s） | §03-V / §03-W |
| chunking | `◐ Chunking` | half-moon spinner | brand-50 #EDF0FF | brand-700 #2A1FAF | brand-500 #4F46E4 determinate | §03-W（PROMPTS 与 parsing 同族） |
| embedding | `◐ Embedding` | half-moon spinner | brand-50 #EDF0FF | brand-700 #2A1FAF | brand-500 #4F46E4 determinate（"embedding 234 / 512 chunks"） | §03-W |
| indexing | `◐ Indexing` | half-moon spinner | brand-50 #EDF0FF | brand-700 #2A1FAF | brand-500 #4F46E4 determinate（"67 / 96"） | §03-V |
| done | `● Ready` | filled dot | success-50 #EBFCF5 | success-700 #047856 | success-500 #10B881 full | §03-V |
| failed | `⊘ Failed` | × | danger-50 #FDF1F1 | danger-700 #B91B1B | danger-500 #EE4444（终止段） | §03-V / §03-Y |

进度条 track 统一 bg-muted #EAEAE5，圆角 999。

---

## §06.W 长任务 4 组件宽度速查表

| 组件 | 宽 | 高 | 圆角 | 背景 | 边框 | 内边距 | 出处 |
|---|---|---|---|---|---|---|---|
| PipelineTree (§06.5 / §03-Y) | 280–320 | flex（嵌入容器） | — | inherit | 节点底 1 border-subtle #E4E4E0 divider | — | §03-Y |
| RunStatsSidebar (§06.6 / §03-Z) | 320 | 784 | 14 | bg-surface #FFFFFF | 1 border-subtle #E4E4E0 | 20 | §03-Z |
| LiveCitationList (§06.7 / §03-AA) | 336 | 784 | 14 | bg-surface #FFFFFF | 1 border-subtle #E4E4E0 | 20 | §03-AA |
| ReviewDraftStreamingView (§06.8 / §03-AB) | 688 | 784 | 14 | bg-surface #FFFFFF | 1 border-subtle #E4E4E0 | 32（gap 16） | §03-AB |

横向三列布局合计：PipelineTree (≤320) + RunStats (320) + Draft (688) + LiveCitation (336) — 与 §03 全局 12-column 1280 max 内容约束一致（gutters 24）。

---

## §06.X 跨组件联动 — 单 SSE 多 subscriber

### 关键抽象 `useTaskStream(taskId)`
```ts
// composables/useTaskStream.ts
import { useEventSource } from '@vueuse/core'

const connections = new Map<string, TaskStreamConnection>()

export function useTaskStream(taskId: string) {
  let conn = connections.get(taskId)
  if (!conn) {
    const ev = useEventSource(`/api/tasks/${taskId}/events`, [], {
      withCredentials: true,
      autoReconnect: { retries: 5, delay: 1000, onFailed: () => toastDanger('Task stream lost') },
    })
    conn = { ev, refs: 0, tree: ref([]), stats: ref({}), draft: ref(''), citations: ref([]) }
    ev.event = (e) => applyTaskEvent(conn!, e)
    connections.set(taskId, conn)
  }
  conn.refs++
  onScopeDispose(() => {
    if (--conn!.refs === 0) {
      conn!.ev.close()
      connections.delete(taskId)
    }
  })
  return { tree: conn.tree, stats: conn.stats, draft: conn.draft, citations: conn.citations,
           status: computed(() => conn!.stats.value.status) }
}
```

要点：
1. **单连接多 subscriber**：同 taskId 只开一个 EventSource，ref-count GC；
2. **统一事件归一化**：`applyTaskEvent` 按 `e.type` 分发 (`node.update / stats.update / draft.token / citation.new`)；
3. **后台化**：组件 unmount 时 refs 不减 0（因 tasksStore 永远持有 +1） → 离开页面也不断流，参见 ADR-0010 SSE task progress events；
4. **断网重连**：`autoReconnect` 5 次指数退避；恢复后请求 `?since=<lastEventId>` 走 SSE Last-Event-ID 协议；
5. **粒度**：draft.token 事件每 100 ms 合并 buffer 一次提交，避免 vue patch 风暴。

### ASCII 时序图

```
User                Frontend                       Backend                 Stream
 │                     │                              │                       │
 │  Click "Generate Review"                           │                       │
 │────────────────────>│                              │                       │
 │                     │  POST /reviews               │                       │
 │                     │─────────────────────────────>│                       │
 │                     │                              │  enqueue worker       │
 │                     │  201 { taskId: "rv-873" }    │                       │
 │                     │<─────────────────────────────│                       │
 │                     │                                                      │
 │                     │  useTaskStream("rv-873")                             │
 │                     │  ├─ if no conn: new EventSource /tasks/rv-873/events │
 │                     │  └─ refs=1                                           │
 │                     │─────────────────────────────────────────────────────>│
 │                     │                                                      │
 │                     │                              SSE: node.update (ingest done)
 │                     │<─────────────────────────────────────────────────────│
 │                     │  applyTaskEvent → tree.update / stats.update         │
 │                     │  ├─ PipelineTree 组件 reactive 渲染                  │
 │                     │  ├─ RunStatsSidebar 组件 reactive 渲染               │
 │                     │  ├─ LiveCitationList 组件 reactive 渲染              │
 │                     │  └─ ReviewDraftStreamingView 组件 reactive 渲染      │
 │                     │                                                      │
 │  Click "Run in bg"  │                                                      │
 │────────────────────>│  tasksStore.background(taskId)                       │
 │                     │  refs += 1 (perma-hold), 弹出 mini bubble            │
 │                     │  路由跳转到 /lib/:id（PipelineTree 卸载，refs -1）   │
 │                     │  EventSource 继续，因为 store 持有                   │
 │                     │                                                      │
 │                     │                              SSE: task.done          │
 │                     │<─────────────────────────────────────────────────────│
 │                     │  全局 toast "Draft ready · 3,012 words"              │
 │                     │  mini bubble 变 "View"                               │
 │                     │                                                      │
 │  Click "View"       │                                                      │
 │────────────────────>│  路由回 /tasks/rv-873                                │
 │                     │  ReviewDraftStreamingView mount → useTaskStream      │
 │                     │  refs += 1，复用同一连接（如未关）或拉历史 snapshot  │
 │                     │                                                      │
```

---

## §06.Z 三条不可破规范

1. **同一 taskId 永远只能有一个 EventSource**。所有进度类组件必须经由 `useTaskStream(taskId)` 订阅；禁止任何组件直接 `new EventSource` 或单独轮询。违者 → ESLint 自定义规则 `no-direct-eventsource` 标 error。

2. **SHA-256 客户端先算 + 后端 `/docs:check` 比对，命中已存在不报错只标记 "deduped"**。任何上传路径必须走 `ingestStore.enqueue()`，禁止页面级组件直接 POST `/docs`。SHA-256 必须在 Web Worker 中算，禁止占用主线程超过 16 ms。

3. **长任务（任何 `taskId` 已注册到 `tasksStore`）的 SSE 连接生命周期由 `tasksStore` 持有，而不是组件**。组件 unmount 不应关闭流。`Run in bg` 是显式将连接所有权移交 store；用户主动取消或 `task.done` 之后 30 s 才允许 store 释放连接。
