# 04 · Chat / Evidence / Citation 交互规范

> 范围：S3 旗舰屏 `/lib/:id/chat`（Nav + Conversation + EvidencePanel 三栏）  
> 哲学：**Citation-first** — LLM 输出的任何事实陈述都必须以可点击的 CitationChip 出现，前端在渲染层做白名单过滤。  
> SSE 协议：`event: meta | token | citations | done | error`  
> 适用图：032 / 033 / 034 / 035 / 036 / 037 / 038（`G:/anyfast/research-agent/docs/ui-images/`）

---

## 0. 全局共识 (Single Source of Truth)

### 0.1 类型契约（从 `openapi-typescript` 生成）

```ts
// src/types/chat.ts —— 直接 re-export 自 generated/api.d.ts
export interface Citation {
  id: string            // "03-i" 形态，前端唯一键
  chunkId: string       // 反向定位到 EvidenceCard
  docId: string
  page?: number
  score: number         // 0..1
  retriever: 'vector' | 'bm25' | 'graph' | 'community'
  snippet: string       // 命中片段（带 <mark> 占位）
  source: 'pdf' | 'web' | 'note'
}
export interface QAResponse {
  messageId: string
  text: string
  citations: Citation[]
  reasoning?: ReasoningStep[]
  usage: { promptTok: number; completionTok: number; cost: number }
}
export interface ReasoningStep {
  index: number
  kind: 'plan' | 'retrieve' | 'rerank' | 'expand' | 'verify' | 'synthesize'
  label: string
  toolCalls: { name: string; durMs: number; tokens?: number; score?: number }[]
}
```

### 0.2 Pinia store 拓扑（store 不与 component 直耦合）

```
chatStore          ← 会话主体 / 流式状态机
  ├─ sessions: Record<sessId, Session>
  ├─ activeSessionId
  ├─ streaming: { sessId, msgId, status, abortCtl }
  └─ citationsIndex: Record<msgId, Map<citId, Citation>>   // ★ 渲染时白名单
evidenceStore       ← 右栏证据
  ├─ activeCitationId   // chip click 写入
  ├─ pinnedEvidence: Citation[]   // "Pin to chat" 集合
  └─ queryTokens: string[]        // 用于命中文本高亮分词
composerStore       ← Composer 输入态（draft per sessionId）
  ├─ drafts: Record<sessId, { text, attachments, model }>
  ├─ mention: { open, query, kind, anchor }
  └─ tokenEstimate: number
reasoningStore      ← 折叠 UI 局部状态
  └─ expanded: Set<msgId>
```

> Pinia store 之间通过 `watch(activeCitationId, scrollToCard)` 解耦；component 不直接调用 store-store。

---

## 1. CitationChip — 内联引用 chip（★ 旗舰组件）

参考：`032-03-i-citationchip.png`

### 1.1 视觉规范（从 token 文件取色）

| 状态        | bg          | fg          | border | 备注 |
|------------|-------------|-------------|--------|------|
| default    | `#F2F4FF`   | `#5B6CFF`   | none   | 内联高度 18 px，行内对齐 baseline +1 |
| hover      | `#E6EAFF`   | `#3B4DE6`   | none   | 触发 floating preview（350 ms 延迟入场，120 ms 出场） |
| active/clicked | `#5B6CFF` | `#FFFFFF` | none   | 同步 evidenceStore.activeCitationId |
| focus(键盘) | default bg  | default fg  | `2 px #A3B0FF` outline, offset 2 | 不抢焦点时回 default |
| placeholder | `#E5E7EB`  | `#9CA3AF`   | dashed | 流式 token 阶段尚未收到 `citations`，显示 `[?]` |

形态：`<sup>` 体感，圆角 6 px，padding `2px 6px`，font `12/16 SF Mono`，内容形如 `03-i`。

### 1.2 三态生命周期（关键状态机）

```
[hidden]
  │  markdown 解析时遇到 [03-i]
  ▼
[placeholder]            ← SSE token 流入，citationsIndex 中尚无此 id
  │  收到 event: citations，id ∈ whitelist
  ▼
[default]                ← 实化完成；hover 显示预览
  │  user click 或 Enter
  ▼
[active]                 ← 同步 evidenceStore.activeCitationId
  │  300 ms 后 evidence 卡片完成 scrollIntoView + 高亮
  ▼
[default] (deactivate)   ← 切换到其它 chip 或 panel 关闭

# 异常分支：
[placeholder] ── citations 到了但 id 不在 whitelist ──▶ [删除节点]（白名单过滤）
```

### 1.3 渲染时白名单过滤（防 LLM 幻觉）

```ts
// markdown-it custom rule: token 替换
md.inline.ruler.after('text', 'citation', (state) => {
  const m = /^\[([A-Za-z0-9-]{1,12})\]/.exec(state.src.slice(state.pos))
  if (!m) return false
  const id = m[1]
  const tok = state.push('citation_chip', '', 0)
  tok.meta = { id }                              // 渲染期再查 chatStore.citationsIndex
  state.pos += m[0].length
  return true
})

// vue render：拿到 msgId + id，去 store 查白名单
function renderCitation(id: string, msgId: string) {
  const cit = chatStore.citationsIndex[msgId]?.get(id)
  if (!cit && !chatStore.isStreaming(msgId)) return ''  // 静默吞掉幻觉
  if (!cit) return h(CitationChipPlaceholder, { id })   // 流式占位
  return h(CitationChip, { citation: cit })
}
```

### 1.4 交互（鼠 / 键 / 触 / AT）

- **鼠标**：hover → 350 ms 后弹 floating-vue tooltip（标题、作者、年份、snippet 80 字截断、score 进度条）。click → 滚动并打开 EvidencePanel，对应卡片高亮 1.6 s 黄色 `#FFF7C2 → transparent`。
- **键盘**：Tab 可达；Enter / Space 等价 click；同一条消息内多 chip 之间用 `ArrowLeft / ArrowRight` 在自定义 roving-tabindex 中切换（只一个 chip 处于 tabIndex=0）。
- **触摸**：long-press 500 ms 等价 hover（弹预览）；tap 等价 click。
- **AT**：`role="link"`，`aria-label="引用 ${id}, 文档 ${docTitle}, 第 ${page} 页, 相似度 ${score}"`；`aria-describedby` 指向当前 tooltip id（仅展开时）。

### 1.5 动效

- 实化（placeholder → default）：颜色 lerp 200 ms `ease-out`，宽度抖动加 `font-variant-numeric: tabular-nums` 防跳。
- active 切换：scale 0.94 → 1.00 80 ms 弹回，bg 用 `View Transitions API`（不可用时回退到 css transition）。
- preview tooltip：opacity + translateY(4 px) 入场 160 ms。
- 高亮命中卡片：`@keyframes flash` 1600 ms。

### 1.6 Vue 实现骨架

```vue
<!-- src/components/chat/CitationChip.vue -->
<script setup lang="ts">
import { Citation } from '@/types/chat'
import { useEvidenceStore } from '@/stores/evidence'
import { useFloating, offset, flip, shift } from '@floating-ui/vue'
const props = defineProps<{ citation: Citation }>()
const evidence = useEvidenceStore()
const chipRef = ref<HTMLElement>()
const tipRef = ref<HTMLElement>()
const open = ref(false)
const isActive = computed(() => evidence.activeCitationId === props.citation.id)
const { floatingStyles } = useFloating(chipRef, tipRef, {
  placement: 'top', middleware: [offset(6), flip(), shift({ padding: 8 })],
})
function activate() {
  evidence.activate(props.citation.id)   // 写 store → 触发右栏 scroll + 高亮
}
</script>
<template>
  <button ref="chipRef" :class="['chip', isActive && 'chip--active']"
          :aria-label="`引用 ${citation.id}`"
          @click="activate" @keydown.enter.prevent="activate"
          @mouseenter="open = true" @mouseleave="open = false">
    {{ citation.id }}
  </button>
  <Teleport to="body" v-if="open">
    <div ref="tipRef" :style="floatingStyles" class="chip-preview">
      <!-- title / authors / score bar / snippet 80ch -->
    </div>
  </Teleport>
</template>
```

### 1.7 联动

- ← `chatStore.citationsIndex[msgId]`（白名单源）
- → `evidenceStore.activate(id)` → 触发 EvidencePanel autoscroll & highlight
- → 路由 query 同步 `?cite=03-i`（支持分享 deep link）

### 1.8 UI 参数（来自 UI_PROMPTS §03-I）

| 类别 | 值 |
|---|---|
| 宽度 | 26（固定，单数字）；多位数字 auto，min-w 26 |
| 高度 | 20 |
| padding | `2 6`（inline `<sup>` 体感） |
| 字体（编号） | JetBrains Mono 11/13.3 700，center-aligned |
| 颜色（default bg） | `info-50 #EBFDFF` |
| 颜色（default border） | `info-500 #06B6D3 @24%` 1px |
| 颜色（default fg） | `info-700 #0E7490` |
| 颜色（hover bg） | `info-100`（lighten） |
| 颜色（active bg） | `info-100` + outline `brand-500 #4F46E4` 1px |
| 圆角 | 4（chip-radius 变体，inline 密度专用；非通用 chip 6） |
| 焦点环 | `shadow-focus = 0 0 0 3px rgba(79,70,229,.20)`（brand 焦点环） |
| 动效（hover） | 120ms ease-out background-color |
| 动效（preview 入场延迟） | 240ms（PROMPTS）/ 350ms（SPEC §1.1，**冲突 → 以 SPEC 为准**） |
| 动效（streaming caret） | 22ms / token，blink 1.0 Hz |
| 预览卡 | 320 × 140，bg-surface，shadow-md，radius 14 |
| 预览卡 · title | body-sm 600，2 行截断 |
| 预览卡 · meta | caption 12/14.5 400 text-tertiary |
| 预览卡 · quote | 3 行 body-sm 13/15.7 italic，命中词 bg `warning-50 #FFFAEB` |
| 配对正文字 | body 14/22 text-primary `#1A1A1A` |
| 不绘制方括号 | "[" "]" 视觉上不绘，只显示编号 |
| a11y | role=button + aria-describedby → 对应 EvidenceCard id |

> **冲突 1**：PROMPTS 写 hover preview 延迟 240ms；SPEC §1.1 写 350ms。以 SPEC 为准（产品决策更新）。  
> **冲突 2**：PROMPTS 字体使用 Inter 11/13.3，但全局规则中 mono 用于 chunk_ids/DOIs/scores/编号；CitationChip 编号建议 mono（JetBrains Mono），与 SPEC §1.1 `font 12/16 SF Mono` 同族。SPEC 字号 12/16 与 PROMPTS 11/13.3 不一致 → 以 SPEC 为准。  
> **冲突 3**：PROMPTS 圆角 4；SPEC §1.1 圆角 6。以 SPEC 为准。

---

## 2. MessageBubble — 流式消息气泡（★）

参考：`035-03-l-messagebubble-user-vs-assistant.png`

### 2.1 视觉

| 角色      | 头像                       | 容器          | 行高 | 字色     | 备注 |
|----------|---------------------------|--------------|-----|---------|------|
| user     | 圆形 28 px 首字母（首字母深色字 + 浅灰底） | 无气泡描边，宽度自适应至 720 px | 22 | `#0F172A` | 右上 timestamp `· 2m ago` |
| assistant| 品牌钻石 logo（24 px）+ 模型名 "Claude Haiku 4.5" | 同上，无气泡，左缩进 40 | 24 | `#0F172A` | 底部 meta 行：Show reasoning trace · 6 retrieval steps · 4.2 s · Copy · Regenerate · Helpful 👍 / 👎 |

### 2.2 流式 token 注入（caret 22 ms/token）

- SSE `event: token { delta }` 累加到 `chatStore.streaming.buffer`；
- `useTokenStream(buffer)` composable 节流到 22 ms 一帧，避免 markdown 解析抖动；
- 末尾插入闪烁 caret：`<span class="caret" />`（1 px wide，1 s blink）；
- 收到 `event: done` 时移除 caret，触发 markdown 一次完整重渲染（确保代码块、KaTeX、CitationChip 全部最终化）。

### 2.3 状态

| 状态        | 触发                       | 视觉                                |
|------------|---------------------------|-------------------------------------|
| streaming  | meta 收到后                | caret 闪烁；底部「Stop generating」红色按钮 |
| paused     | 用户切 tab > 30 s          | dim 60%，提示「点击恢复滚动」              |
| interrupted| 用户点 Stop                | 文末显示 `↳ stopped at token 412`，保留已输出 |
| error      | event: error / SSE 断流    | 红色 banner「网络中断」+ Retry；保留已输出 ★ |
| truncated  | context > limit            | 内容前置 `…earlier context omitted` 折叠条 |

### 2.4 hover 工具条

距离右侧 8 px 浮出 IconButton 行：`Copy` `Cite` `Permalink` `Branch from here` `Delete`（≥ assistant 才出 Regenerate）。  
延迟 120 ms 显示 / 80 ms 消失（floating-vue）。

### 2.5 markdown 渲染管道

```ts
import MarkdownIt from 'markdown-it'
import shiki from 'markdown-it-shiki'
import katex from '@vscode/markdown-it-katex'
import { citationPlugin } from './md-plugins/citation'

const md = new MarkdownIt({ html: false, linkify: true, breaks: false })
  .use(shiki, { theme: 'github-light' })
  .use(katex)
  .use(citationPlugin)            // ★ [03-i] → citation_chip token

function renderMarkdown(src: string, msgId: string) {
  const env = { msgId }                  // 透传给 citation_chip renderer
  return md.render(src, env)
}
```

> 关键：`citation_chip` 的渲染器返回的是占位 HTML `<span data-cit="03-i" data-msg="m1" />`，再由 Vue 在 mount 阶段通过 `Teleport` / 自定义指令把它"替换"成真正的 `<CitationChip>` 组件（避免 v-html 损失响应式）。  
> 备选方案：直接用 `vue-markdown-it` 的 vnode 注入器，但实测对自定义 token 不友好；自写 30 行更可控。

### 2.6 A11y

- `role="article"` + `aria-roledescription="message"`；
- 流式时 `aria-live="polite"`，但只在段落 punct 时通知（避免逐 token 轰炸 reader）；
- 工具条 hidden 默认不进入 tab，hover/focus 后用 `aria-hidden=false`；
- 错误 banner `role="alert"`。

### 2.7 动效

- 入场：translateY 8 px → 0、opacity 0 → 1，160 ms `cubic-bezier(.2,.7,.3,1)`。
- "Regenerate" 点击：旧气泡 dim 40%，新气泡从其下方滑入 200 ms（不删除旧气泡，保留分支）。

### 2.8 UI 参数（来自 UI_PROMPTS §03-L）

| 类别 | 值 |
|---|---|
| 容器宽 | 712（Chat 列固定栅格，与 Composer 同宽） |
| 头像 | 28 × 28，round；user bg `brand-50 #EDF0FF` + text `brand-700 #2A1FAF` 600 字母；assistant bg `brand-500 #4F46E4` + 白色钻石符 "◆" |
| 名行字体 | body 14/16.9 600 |
| 相对时间 | caption 12/14.5 text-tertiary `#8C8C82` |
| 正文 | body 14/22 text-primary `#1A1A1A`（无气泡描边、无背景） |
| 左侧对齐缩进 | padding-left 8（user）/ 40（assistant，与 SPEC §2.1 一致） |
| 行高 | 22（与 SPEC §2.1 一致；PROMPTS 写 14/22） |
| 流式 caret | 2 × 16 brand-500 `#4F46E4` 竖条，blink 1Hz（PROMPTS）/ 22 ms/token 节奏一致 |
| 模型名样式 | "RAG-KG · Claude Haiku 4.5" body 14 600 |
| 底部 meta 行 | body-sm text-tertiary，middot 分隔，含 `▾ Show reasoning trace · 6 retrieval steps · 4.2s`、`Copy`、`Regenerate`、`Helpful 👍 / 👎` |
| hover 工具条偏移 | 距右侧 8（SPEC §2.4） |
| hover 工具条延迟 | 显示 120 ms / 消失 80 ms |
| 入场动效 | translateY 8 → 0 + opacity 0 → 1，160 ms `cubic-bezier(.2,.7,.3,1)` |
| Regenerate 动效 | 旧气泡 dim 40%，新气泡下滑 200 ms |
| max-width 比例 | user/assistant 自适应至 720（来自 SPEC §2.1），与容器 712 同序 |
| — | 圆角偏角度 / 触发气泡偏角：PROMPTS **未写**（PROMPTS 明确 "no bubble"，故 N/A） |

---

## 3. EvidenceCard / EvidencePanel — 证据栏（★）

参考：`033-03-j-evidencecard.png` / `034-03-k-evidencepanel.png`

### 3.1 EvidencePanel 形态

- 桌面 ≥ 1280：嵌入式 right column，宽 **440 px**，无遮罩；
- 1024–1279：抽屉，宽 **360 px**，从右滑入 220 ms，背景 dim 30%；
- < 1024：全屏 modal，从 bottom 推上 280 ms；
- header：`Library · neuro-24` 选择 + 关闭 ×；
- 内容：垂直 EvidenceCard 列表 + 「比较」「Pin」「Export」工具条；
- 折叠态：保留 32 px 竖条「Evidence (n)」可点击展开。

### 3.2 EvidenceCard 视觉（4 retriever × 3 态 = 12 卡）

retriever 角标色：vector `#5B6CFF` · bm25 `#F59E0B` · graph `#10B981` · community `#A855F7`。

| 部位           | 规范 |
|---------------|------|
| 左侧色条 4 px  | retriever 主色 |
| top            | 文档标题 + 年份 + venue badge |
| middle         | snippet（最多 4 行，命中 query token 用 `<mark style="background:#FEF3C7">` 高亮） |
| bottom-left    | retriever icon + score bar (0..1) |
| bottom-right   | Pin 图标 / Open in viewer / Cite as `[03-i]` |
| hover          | `box-shadow 0 6px 18px rgba(91,108,255,.12)` + 上移 2 px |
| active         | `border 2 px solid #5B6CFF` + bg `#F7F8FF`，scroll 后自动滚到 viewport 中部 |

### 3.3 命中高亮分词器（client 侧）

```ts
// 极简但够用：去重 + 长度≥2 + 去停用词 + 转义 regex
function tokenize(query: string): string[] {
  const stop = new Set(['the','and','of','to','a','in','on','for','is','with'])
  return [...new Set(query.toLowerCase().match(/[\p{L}\p{N}]{2,}/gu) ?? [])]
    .filter(t => !stop.has(t))
}
function highlight(snippet: string, tokens: string[]): string {
  if (!tokens.length) return snippet
  const re = new RegExp(`(${tokens.map(escapeRegex).join('|')})`, 'gi')
  return snippet.replace(re, '<mark>$1</mark>')
}
```

> 中文场景：替换为 `intl-segmenter`（浏览器原生 `Intl.Segmenter('zh', { granularity: 'word' })`）。

### 3.4 联动

- `watch(evidence.activeCitationId, async id => { await nextTick(); cardRef[id]?.scrollIntoView({ behavior: 'smooth', block: 'center' }); cardRef[id]?.classList.add('flash') })`
- "Pin to chat" → `evidenceStore.pinnedEvidence` → 在 chat 顶端显示固定证据条（最多 3 个，超出 stacked）。
- panel 关闭时不重置 `activeCitationId`（再次打开仍回到原位）。

### 3.5 A11y

- panel `role="complementary"` + `aria-label="证据栏"`；
- 卡片 `role="article"` + 可聚焦（tabindex=0）+ Enter 等价"打开 viewer"；
- 命中 `<mark>` 默认 reader 会读出 "highlighted"，需要时用 `aria-label` 注入完整 snippet。

### 3.6 EvidenceCard UI 参数（来自 UI_PROMPTS §03-J）

| 类别 | 值 |
|---|---|
| 卡尺寸 | 392 × 196 |
| 圆角 | 14（card radius） |
| bg | `bg-surface #FFFFFF` |
| border | 1px `border-subtle #E4E4E0` |
| padding | 16 |
| 内 gap | 8 |
| top · 标题 | h4 18/21.8 600，max 2 lines |
| top · CitationChip 引用 | 26 × 20，info 样式（同 §1.8） |
| meta 行 | caption 12/14.5 text-tertiary，格式 `Author et al. · Year · Venue` |
| quote 块 | body-sm 13/15.7 text-secondary italic，1px dashed `border-subtle`，padding 12，3 行 max |
| 命中高亮 bg | `warning-50 #FFFAEB`（PROMPTS）/ SPEC §3.2 用 `#FEF3C7` + flash `#FFF7C2 → transparent` 1.6s |
| footer · 元数据 pill | 最多 3 条，middot 分隔，mono caption text-tertiary |
| footer · score | mono-sm 600 `brand-700 #2A1FAF` |
| source 图标尺寸 | Lucide 14，text-tertiary（vector=`axis-3d`, bm25=`type`, graph=`git-branch`, community=`users`） |
| hover | shadow-sm `0 1px 2px rgba(15,15,20,.04)` |
| selected（active citation 联动） | border `brand-500` 1px + 左侧 4 px brand-50 accent rail |
| 列表间距 | 16（EvidencePanel body gap） |

> **冲突 4**：PROMPTS source 角标色与 SPEC §3.2 retriever 色不一致：  
>   - vector：PROMPTS 用 Lucide 图标灰色 / SPEC 用 `#5B6CFF`（与 brand-500 `#4F46E4` 不同源）→ 以 SPEC 为准。  
>   - bm25：PROMPTS 未指定 / SPEC `#F59E0B` ≈ warning-500。  
>   - graph：SPEC `#10B981`，PROMPTS Concept/Method 类似 `#10B881`。  
>   - community：SPEC `#A855F7`，PROMPTS Author `#A854F7` ≈ 同。  
> **冲突 5**：accent rail PROMPTS 左 4 px / SPEC §3.2 左 4 px 色条 + active 卡片 2 px border。以 SPEC 为准（双重视觉）。

### 3.7 EvidencePanel UI 参数（来自 UI_PROMPTS §03-K）

| 类别 | 值 |
|---|---|
| 宽度 · Chat（≥1280） | 440 |
| 宽度 · KG 视图 / 紧凑 | 360 |
| 宽度 · 抽屉态（1024–1279） | 360（与 SPEC §3.1 一致） |
| 宽度 · 折叠 rail | 56（PROMPTS）/ SPEC §3.1 写 32 px 竖条 → **冲突 6**：以 SPEC 32 为准 |
| 高度 | 整高（topbar 下方 = 视口高 - 56） |
| bg | `bg-surface #FFFFFF` |
| border | 左 1px `border-subtle #E4E4E0` |
| padding | 24 |
| 内部 gap | 16（EvidenceCard 之间） |
| header h3 | 20/24.2 600 "Evidence" |
| header meta | caption 12/14.5 text-tertiary `3 sources cited · click [n] in answer to jump` |
| 折叠按钮 icon | Lucide `panel-right-close`，右对齐，stroke 1.5，尺寸 20 |
| 折叠态指示 | 折叠 rail 内画 3 个 mini dot（cited source 计数） |
| chip 点击 → 高亮卡 | 240 ms `brand-50` 洗背 + smooth scroll-into-view（SPEC §3.4 写 1.6 s flash） |
| 滚动条样式 | 默认（PROMPTS 未指定） |
| pinned 区域 | PROMPTS 未指定（SPEC §3.4 写最多 3 个 pinned 在 chat 顶端，超出 stacked） |

---

## 4. ReasoningTrace — 推理过程展开

参考：`036-03-m-reasoningtrace-toggle.png`

### 4.1 视觉

- 默认折叠成单行 `▸ Show reasoning trace · 6 retrieval steps · 4.2 s`。
- 展开后渲染为带左色条 `#5B6CFF` 的步骤列表，每行：序号圆 → 图标 → 标签 → 元数据 `128 tok · 0.3 s · score 0.91`。
- step 整行 hover 时显示「View tool call」侧出抽屉。

### 4.2 交互

- Toggle 用 `<details>` 原生元素 + 自定义样式（保证 reader 与 Ctrl+F 都能找到内容）；
- step click → 弹小抽屉，展示 tool name、input args（折叠 JSON）、output preview、durMs；
- 每个 step 有 `data-kind`，可用于 e2e 选择器。

### 4.3 动效

- height auto 不可过渡 → 用 `grid-template-rows: 0fr → 1fr` 技巧实现 220 ms ease。

### 4.4 UI 参数（来自 UI_PROMPTS §03-M）

| 类别 | 值 |
|---|---|
| 折叠态行 | 单行 body-sm 13/15.7 text-tertiary `▾ Show reasoning trace · 6 retrieval steps · 4.2s` |
| 折叠按钮组件 | 原生 `<details>`（SPEC §4.2） |
| 展开 · 左色条 | 2 px vertical rail `brand-200 #B2BCF4`（PROMPTS）/ SPEC §4.1 写 `#5B6CFF` → **冲突 7**：以 SPEC 为准 |
| 展开 · padding | 12 |
| 步骤行 · 序号圆 | 20 × 20，bg `bg-subtle #F4F4F1`，text body-sm 600 text-secondary |
| 步骤行 · 标题 | body-sm 13/15.7 text-primary（如 `Retrieve · vector top-K=12 in graphrag-survey`） |
| 用时 chip 样式 | mono caption 11/13.3 text-tertiary（如 `412 tok · 1.2s · score 0.91`，tabular-nums） |
| 步骤 icon | Lucide stroke 1.5 尺寸 16：`compass`（plan）/`search`（retrieve）/`filter`（rerank）/`sparkles`（synthesize）/`check`（verify） |
| 总步数（示例） | 6（含 `Synthesize answer · 1,824 tok · 2.1s` 末行） |
| 展开/收起动效 | `grid-template-rows: 0fr → 1fr` 220 ms ease |

---

## 5. Composer — 输入区（★ 最重要）

参考：`037-03-n-composer.png`

### 5.1 形态

- 容器 max-width 760 px 居中；高度自适应 `min 56 / max 240 px`（超出则纵向滚动）；
- 左下 attachments 区（拖拽 + chip 列表）；
- 中部 textarea，placeholder `Ask anything in this Library… type "/" for commands`；
- 右下：token 计数 `8 docs · 320 tok` + 模型选择 `Claude Haiku 4.5 ▾` + 主按钮 `Send ↵`；
- 顶部条：预算超限时浮一条 `Budget exceeded — Adjust budget` 红色提示。

### 5.2 自适应高度（不用 lib，5 行原生）

```ts
// composables/useAutosize.ts
export function useAutosize(el: Ref<HTMLTextAreaElement | undefined>, max = 240) {
  watchEffect(() => {
    const t = el.value; if (!t) return
    t.style.height = '0px'
    t.style.height = Math.min(t.scrollHeight, max) + 'px'
    t.style.overflowY = t.scrollHeight > max ? 'auto' : 'hidden'
  })
}
```

> 选择 `@vueuse/core useTextareaAutosize` 也可（已经在依赖里），但自写避免一次响应式订阅。

### 5.3 键位（必须 100% 一致）

| 键              | 行为                                                 |
|----------------|------------------------------------------------------|
| Enter          | 发送（若 mention dropdown 打开，则选中候选）           |
| Shift + Enter  | 换行                                                |
| ⌘/Ctrl + Enter | 强制发送（即使 IME composition 进行中，先 finalize 再发）|
| Esc            | 关闭 mention dropdown；连按两次清空输入并存草稿        |
| /              | 触发 slash-command 面板（仅当光标在行首或前为空格）     |
| @              | 触发实体 mention（kg entity / docId）                |
| ↑（光标空时）   | 编辑上一条用户消息                                    |
| Tab            | mention 打开时切换候选，否则插入两空格               |

### 5.4 Slash command dropdown

参考图中 5 项：`/review` `/reason` `/hypothesis` `/cite` `/iterate`。

```ts
// 触发条件：光标前缀匹配 /^\/(\w*)$/，用 @floating-ui/vue 锚定到光标位置
const triggers = {
  '/': loadSlashCommands,   // 静态 + 用户最近
  '@': loadEntityMentions,  // 调 /api/entities?prefix=...
  '#': loadDocMentions,     // 调 /api/docs?prefix=...
}
```

- 候选 ≤ 6 行，键盘 ↑↓ 切换，Enter / Tab 选中；
- 选中后插入文本如 `/review topic:` 并把光标停在 `topic:` 之后；
- mention 候选条 hover 显示二级 tooltip（实体描述）。

> 推荐 lib：**`@floating-ui/vue`**（不是 tribute.js — tribute 不支持 IME 良好，且 DOM 注入式与 Vue 不和）。自写一个 200 行 `MentionPopover.vue`，比 lib 都好维护。

### 5.5 文件拖拽

- 整个 conversation 列被设为 dropzone；拖入时整列 dashed border + 中央 hint；
- drop 后文件作为 chip 出现在 Composer 左下；最多 8 个 / 50 MB；
- 上传立刻开始（PUT `/uploads/presign` → S3），chip 上画 progress ring；
- 若同 sessionId 中已有同 hash 文件，前端去重并提示「already attached」。

### 5.6 提交流程（乐观 UI + SSE 订阅）

```
submit()
  1. composerStore.validate()                # 文本非空 / token < limit
  2. const tempMsgId = nanoid()
  3. chatStore.appendUserMessage({ tempMsgId, text, attachments })   # 乐观插入
  4. chatStore.startStream({
       sessionId, prompt: text, attachments,
       onMeta, onToken, onCitations, onDone, onError
     })
  5. composerStore.clearDraft(sessionId)     # 但保留 attachments 引用
  6. focus 回 textarea，光标置首
```

错误回滚：`onError` 时 user 气泡保留并加红色 retry 按钮（不要删除已输入的内容）。

### 5.7 草稿持久化

```ts
// per sessionId 草稿，刷新 / 切换 session 不丢
const draft = useStorage(`chat-draft:${sessionId.value}`, '', localStorage, {
  mergeDefaults: true,
})
```

### 5.8 A11y

- textarea `aria-label="提问"`；
- mention dropdown `role="listbox"`，候选 `role="option"` + `aria-selected`；
- token 超额时 `aria-live="assertive"` 通报 1 次（不重复）；
- Send 按钮在流式中变为 Stop，标签也同步：`aria-label="停止生成"`。

### 5.9 动效

- mention dropdown 入场 120 ms，scale 0.96 → 1；
- Send 点击 ripple 取消（避免与 SSE 状态机视觉冲突），改为按钮 → spinner morph 200 ms。

### 5.10 UI 参数（来自 UI_PROMPTS §03-N）

| 类别 | 值 |
|---|---|
| 容器宽 | 712（PROMPTS）/ SPEC §5.1 max 760 居中 → **冲突 8**：以 SPEC 为准 |
| 高度 min | 112（PROMPTS）/ 56（SPEC §5.1）→ **冲突 9**：以 SPEC 为准（更紧凑） |
| 高度 max | 224（PROMPTS）/ 240（SPEC §5.1）→ 以 SPEC 240 为准 |
| 圆角 | 14 |
| bg | `bg-surface #FFFFFF` |
| shadow | shadow-md `0 4px 12px rgba(15,15,20,.06)` |
| border | 1px `border-subtle #E4E4E0` |
| padding | `12 16`（上下 12 / 左右 16） |
| textarea 字体 | body 14/22 text-primary |
| textarea placeholder | text-tertiary `#8C8C82`，文案 `Ask anything in this Library…    type "/" for commands` |
| 底部行高 | 36 |
| Library Pill | 152 × 28，radius pill 999，bg `brand-50`，text `brand-700 #2A1FAF`，前导 dot `brand-500`，body-sm |
| Model 选择器 | body-sm 13/15.7 600 text-secondary + caret `▾`（如 `Claude Haiku 4.5 ▾`） |
| Budget chip | body-sm text-tertiary（如 `Budget · 8 steps · 32k tok`） |
| Slash hint pill | body-sm text-tertiary `/` |
| Send 按钮 | 72 × 32，radius 10，bg `brand-500 #4F46E4`，text 白色 body-sm 600 `⌘↩ Send` |
| Send disabled | 文本空时；loading 显示 spinner |
| token 计数器位置 | 右下（SPEC §5.1：`8 docs · 320 tok` body-sm text-tertiary） |
| 文件拖拽热区 | 整个 conversation 列（SPEC §5.5），dashed border 提示 |
| 拖拽上限 | 8 个 / 50 MB（SPEC §5.5） |
| Slash 命令下拉 | 320 × 220，radius 14，shadow-lg，anchored bottom-left |
| Slash 项 · icon | 16 leading |
| Slash 项 · 名称 | body-sm 600 |
| Slash 项 · 描述 | body-sm text-tertiary |
| Slash 候选数上限 | 6（SPEC §5.4） |
| 空状态示例 chip | 横排 3 个，bg `bg-subtle #F4F4F1`，radius pill 999，body-sm |
| 超预算横幅高度 | 32 |
| 超预算横幅 bg | `danger-50 #FDF1F1` |
| 超预算文案 | `Budget exceeded. Increase or simplify the question.` + `Adjust budget` link |
| Send 焦点环 | shadow-focus `0 0 0 3px rgba(79,70,229,.20)` |

---

## 6. SessionList Item — 会话条目

参考：`038-03-o-sessionlist-item.png`

### 6.1 视觉

- 行高 44 px，icon 16 px + title 14/20 + meta 12/16 ago time（右对齐灰）；
- active：左 3 px solid `#5B6CFF`，bg `#F2F4FF`；
- pinned：title 前加 `★`（深紫色）；
- unread：title 右侧 6 px dot `#EF4444`。

### 6.2 交互

- click → 切 active session（push route `/lib/:id/chat?session=...`）；
- right-click / long-press / 右滑菜单：`Rename` `Pin` `Archive` `Export (md/json)` `Delete`（红色，要二次确认）；
- rename inline：双击 title 变 input，Esc 取消 / Enter 提交；
- 多选：⌘/Ctrl + click 进入多选，底栏出现批量操作。

### 6.3 虚拟滚动

```vue
<RecycleScroller :items="sessions" :item-size="44" key-field="id" v-slot="{ item }">
  <SessionListItem :session="item" />
</RecycleScroller>
```

> 仅在 `sessions.length > 100` 时启用 `vue-virtual-scroller`，否则普通渲染（DOM 数少时虚拟滚动反而引发首屏卡顿）。

### 6.4 A11y

- 列表 `role="listbox"` + `aria-activedescendant`；
- 每项 `role="option"` + `aria-selected`；
- 删除二确认 modal `role="alertdialog"`。

### 6.5 UI 参数（来自 UI_PROMPTS §03-O）

| 类别 | 值 |
|---|---|
| 行尺寸 | 216 × 40（PROMPTS）/ SPEC §6.1 行高 44 → **冲突 10**：以 SPEC 为准 |
| padding | `0 12` |
| 圆角 | 8 |
| hover bg | `bg-subtle #F4F4F1` |
| leading icon | Lucide `message-square` 16，text-tertiary |
| 标题（title） | body-sm 13/15.7 text-primary，truncate 1 line |
| trailing 时间 | caption 12/14.5 text-tertiary，右对齐，相对时间（`now` / `14m` / `3 days`） |
| active bg | `brand-50 #EDF0FF` |
| active text | `brand-700 #2A1FAF` |
| active accent rail | 3 × 28，`brand-500 #4F46E4`，左边缘 |
| section header | meta 11/13.3 500 uppercase text-tertiary（如 `RECENT SESSIONS`） |
| unread dot | 6 px，`danger-500 #EE4444`，title 右侧（SPEC §6.1） |
| pinned star | `★` 深紫色，title 前缀（SPEC §6.1） |
| 右键 / 长按菜单宽 | PROMPTS **未写**；SPEC §6.2 菜单项：`Rename` `Pin` `Archive` `Export (md/json)` `Delete` |
| 虚拟滚动阈值 | sessions.length > 100 启用（SPEC §6.3） |

---

## 7. SSE 客户端 composable（`useSSEChat`）

> 选择 **`@microsoft/fetch-event-source`** 而非原生 `EventSource`：原因 — 原生只支持 GET、不支持 headers（Authorization）；fetch-event-source 支持 POST + 自定义 headers + abort + 自动重连。

### 7.1 API

```ts
export function useSSEChat() {
  const ctl = ref<AbortController | null>(null)
  async function start(opts: {
    sessionId: string
    prompt: string
    attachments?: string[]
    onMeta: (m: { messageId: string; model: string }) => void
    onToken: (t: { delta: string; index: number }) => void
    onCitations: (c: Citation[]) => void
    onDone: (final: QAResponse) => void
    onError: (e: Error) => void
  }) {
    ctl.value = new AbortController()
    await fetchEventSource(`/api/chat/${opts.sessionId}/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: bearer.value },
      body: JSON.stringify({ prompt: opts.prompt, attachments: opts.attachments }),
      signal: ctl.value.signal,
      openWhenHidden: true,           // tab 进入后台仍保持流
      onmessage(ev) {
        switch (ev.event) {
          case 'meta':       return opts.onMeta(JSON.parse(ev.data))
          case 'token':      return opts.onToken(JSON.parse(ev.data))
          case 'citations':  return opts.onCitations(JSON.parse(ev.data))
          case 'done':       return opts.onDone(JSON.parse(ev.data))
          case 'error':      return opts.onError(new Error(ev.data))
        }
      },
      onerror(err) { opts.onError(err); throw err },   // throw 阻止 lib 自动重连
    })
  }
  function stop() { ctl.value?.abort() }
  return { start, stop }
}
```

### 7.2 智能 autoscroll

```ts
// composables/useSmartAutoscroll.ts
export function useSmartAutoscroll(scrollEl: Ref<HTMLElement | undefined>) {
  const stuckToBottom = ref(true)
  const { arrivedState, directions } = useScroll(scrollEl, { throttle: 50 })
  watch(() => arrivedState.bottom, b => { if (b) stuckToBottom.value = true })
  watch(() => directions.top, up => { if (up) stuckToBottom.value = false })   // ★ 用户向上拉 → 停 autoscroll
  function append() {
    if (stuckToBottom.value && scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    }
  }
  return { stuckToBottom, append }
}
```

UI：当 `stuckToBottom = false` 且有新 token 时，右下角浮 `↓ N 条新消息` 按钮，点击恢复 autoscroll。

### 7.3 流式打字机节流（22 ms/帧）

```ts
export function useTokenStream() {
  const buffer = ref('')
  const queue: string[] = []
  let timer: number | null = null
  function push(delta: string) {
    queue.push(delta)
    if (timer == null) timer = window.setInterval(() => {
      if (!queue.length) { clearInterval(timer!); timer = null; return }
      buffer.value += queue.shift()
    }, 22)
  }
  function flush() { buffer.value += queue.join(''); queue.length = 0 }
  return { buffer, push, flush }
}
```

`event: done` 收到时调 `flush()`，避免最后几个 token 还在队列里。

---

## 8. 推荐技术栈（每条带选择理由）

| 关注点         | 推荐                                    | 替代                | 理由 |
|---------------|----------------------------------------|--------------------|------|
| SSE           | `@microsoft/fetch-event-source`         | 原生 EventSource    | POST + headers + abort 必需 |
| Markdown      | `markdown-it` + `markdown-it-shiki` + `@vscode/markdown-it-katex` | marked / remark | 插件生态成熟，可自定义 inline rule 注入 chip |
| 代码高亮      | shiki（VSCode 同款）                    | highlight.js        | 主题一致、CSS 输出体积小、SSR 友好 |
| 浮层          | `@floating-ui/vue`                      | floating-vue        | 更接近底层、可控、tree-shake 友好；floating-vue 适合简单 tooltip |
| 虚拟滚动      | `vue-virtual-scroller`                  | virtua              | 成熟、API 简单；超长（>10k）会话才考虑 virtua |
| 自动滚动      | `@vueuse/core useScroll` + 自写智能停   | 全自动 lib          | 智能停是关键，lib 不提供 |
| Autosize      | 自写 `useAutosize`                      | `useTextareaAutosize` | 5 行解决，避免引入 |
| 本地存储      | `@vueuse/core useStorage`               | localStorage 直写   | 自动 JSON + 跨标签同步 |
| 类型          | `openapi-typescript` 生成               | 手写 d.ts          | 唯一信源在后端 OpenAPI |
| 状态          | Pinia                                   | Vuex / Zustand     | Vue 官方推荐、Composition API 友好 |

> 两个"非显然"推荐再强调：  
> 1. **`@microsoft/fetch-event-source`** — 原生 EventSource 不能加 Authorization header，本项目必须用 POST 携带大 prompt。  
> 2. **`vue-virtual-scroller` 仅在 >100 项启用** — 小列表强行虚拟反而首屏卡顿。

---

## 9. 时序图：用户敲 Enter → 渲染完成

```
User                Composer          chatStore         useSSEChat        Backend           EvidenceStore         UI
 |  type & Enter     |                  |                  |                |                  |                    |
 |─────────────────▶ |                  |                  |                |                  |                    |
 |                   | validate()       |                  |                |                  |                    |
 |                   | appendUserMsg ─▶ |                  |                |                  |                    |
 |                   |                  | optimistic push  |                |                  |  user bubble 立即出 |
 |                   | startStream() ──▶|                  |                |                  |                    |
 |                   |                  | streaming=true   |                |                  |  "Stop" 按钮替换 Send|
 |                   |                  |                  | fetchES POST ─▶|                  |                    |
 |                   |                  |                  |                | event: meta      |                    |
 |                   |                  | ◀────────────── onMeta            |                  |  assistant 骨架显示  |
 |                   |                  |                  |                | event: token×N   |                    |
 |                   |                  | buffer += delta  |◀── onToken ────|                  |  caret + 22 ms 打字  |
 |                   |                  |  (节流 22 ms)    |                |                  |                    |
 |                   |                  |                  |                | event: citations |                    |
 |                   |                  | citationsIndex ◀─| onCitations    |                  |  [?] → 实化为 chip   |
 |                   |                  | activate first ──┼──────────────────────────────────▶ |  EvidencePanel 自动 |
 |                   |                  |                  |                |                  |  scroll + flash 高亮 |
 |                   |                  |                  |                | event: done      |                    |
 |                   |                  | flush + commit ◀─| onDone          |                  |  caret 消失、meta 行  |
 |                   |                  | streaming=false  |                |                  |  reasoning trace 可展开|
```

中断分支：用户点 Stop → `useSSEChat.stop()` → `ctl.abort()` → `onError` 触发 → chatStore 标记 `interrupted`，**保留 buffer 已渲染内容**，文末追加灰色 `↳ stopped at token N`。

---

## 10. 三条这层"绝不能错"的交互

1. **CitationChip 必须做渲染期白名单过滤** — `chatStore.citationsIndex[msgId]` 是唯一信源；markdown 里出现的 `[xx-yy]` 若不在 whitelist 且当前不在流式状态，**静默删除节点**（绝不画 placeholder 也不画错位 chip）。流式中允许显示 `[?]` placeholder，但 `done` 后仍未匹配则降级为纯文本灰字。这是防止 LLM 幻觉污染证据链的最后一道防线。

2. **autoscroll 必须"用户向上拉则停止"** — 流式输出时默认贴底滚动，但只要用户 scroll up（`directions.top === true`），立刻锁定 `stuckToBottom = false` 并显示「↓ N 条新消息」按钮；用户回到底部或点该按钮才恢复。简单地 `scrollTop = scrollHeight` 是 90% 聊天 UI 翻车的根因。

3. **流式中断必须保留已输出内容** — Stop / 网络中断 / token 超限 / SSE 重连失败时，**禁止清空 message buffer**；将状态切换到 `interrupted | error`，追加灰色提示与 Retry/Regenerate 按钮。citations 中已收到的 chip 必须保留实化态（用户可能基于"半截答案"继续查证）。

---

## 11. S3 Chat 旗舰屏 Layout 精确表（来自 UI_PROMPTS §03-I..O + SPEC Figma frame `[S3] 1440×900`）

### 11.1 整体 Grid（桌面 ≥ 1280）

| Grid 区 | 宽度 | 高度 | 断点行为 |
|---|---|---|---|
| Topbar | 1fr（视口宽） | 56 | 固定，不可折叠 |
| SideNav（SessionList 容器） | 240 | 视口高 - 56（=844 @900px） | <lg 折叠成 Tab；<md 抽屉 |
| Conversation（含 MessageBubble + Composer） | 1fr | 视口高 - 56 | min-w 480；中间居中 max-w 760 |
| EvidencePanel · 展开（Chat 默认） | 440 | 视口高 - 56 | <lg 折叠 rail / 抽屉 360 |
| EvidencePanel · 紧凑（KG 视图） | 360 | 视口高 - 56 | md 断点用 |
| EvidencePanel · 折叠 rail | 32（SPEC §3.1）/ 56（PROMPTS） | 视口高 - 56 | 全断点可见；冲突以 SPEC 32 为准 |

### 11.2 Conversation 列内部

| 区 | 宽度 | 高度 | 备注 |
|---|---|---|---|
| Session 元信息行 | 712 | 24 | session date + title，居中 |
| 消息流 | 712 | flex 1 | 居中，max-w 720 自适应 |
| Composer | 712（PROMPTS）/ 760（SPEC） | 56–240（SPEC §5.1） | sticky bottom，gap-top 16 |
| 拖拽热区 | 整列 | 整列 | drop 时整列 dashed border |

### 11.3 SideNav 内部

| 区 | 宽度 | 高度 | 备注 |
|---|---|---|---|
| 内边距 | 240 | — | padding 12 |
| Nav item | 216 | 36 | radius 8 |
| Active nav 背板 | 216 | 36 | bg `brand-50` + 左 3 × 28 brand-500 rail |
| Section header | 216 | 20 | meta uppercase text-tertiary |
| mini-stats panel | 216 | 180 | bg-subtle，radius 10 |
| RECENT SESSIONS 区 · 行 | 216 | 40（PROMPTS）/ 44（SPEC） | 以 SPEC 44 为准 |

### 11.4 EvidencePanel 内部

| 区 | 宽度 | 高度 | 备注 |
|---|---|---|---|
| Header h3 | — | 24（h3 line-height） | 24 padding-top |
| Header meta | — | 16 | caption text-tertiary |
| 折叠 icon | 20 | 20 | Lucide `panel-right-close`，右对齐 |
| 卡片宽 | 392 | 196 | radius 14，gap 16 |
| 内边距 | — | — | 24 |
| 折叠 rail | 32 | 视口高 - 56 | 含纵向 mini dot 列（cited 计数） |

### 11.5 关键 z-index 与 sticky

| 层 | z-index | 备注 |
|---|---|---|
| Topbar | 30 | sticky top 0 |
| Composer | 20 | sticky bottom 0 |
| Slash 命令下拉 / mention popover | 50 | Teleport to body |
| CitationChip preview tooltip | 60 | Teleport to body，跟随 chip |
| EvidencePanel 抽屉态遮罩 | 40 | bg dim 30% |
| Modal（删除确认等） | 100 | 全屏，bg dim |

> **冲突 8/9 合并提醒**：Composer 宽度（712 vs 760）/ min-height（112 vs 56）在 SPEC 与 PROMPTS 之间不一致；表中已标注，统一以 SPEC 为准（前端实现唯一源）。
