# AI 提示词使用指南 — 把这套规范交给 AI 完成前端

> 本文件是"如何使用 `ui-interaction-spec/` 让 AI 实施完整 RAG-KG Copilot 前端"的操作手册。

---

## 0. 这个文件夹里有什么 / 缺什么

### 已包含（11 份文档）
- `UI_INTERACTIONS.md` — 总入口 + 6 条全局红线
- `FRONTEND_TECH_STACK.md` — Vue 库选型 + `package.json` + store 划分
- `01–08-*.md` — 8 份组件级 UX 规范
- `AI_PROMPT_GUIDE.md` — 本文件

### 默认未包含（需要你决定）
- **90 张设计图 PNG** — 真图在 `docs/ui-images/`（仓库根 docs 下）
- **`UI_GALLERY.md`** — 视觉图集索引

→ **如要做自包含包**：把它们也复制进 `ui-interaction-spec/`。AI 看图能力远强于看文字描述，强烈建议复制。

→ **不复制时**：在提示词里使用 `docs/ui-images/...` 绝对/相对路径，AI 仍可读，但要求 AI 有跨目录文件访问权限（Claude Code / Cursor 可以，普通 ChatGPT 网页不行）。

### 完全未包含（按需自行补齐）
- `docs/FRONTEND_DESIGN_SPEC.md`（Figma 实测 token + 14 frame 层级）
- `docs/FRONTEND_RULES.md` / `docs/FRONTEND_CODING_STANDARDS.md`
- `docs/PROJECT_OVERVIEW.md` / `docs/PRD.md`（业务背景）
- 运行时 `/openapi.json`（后端启动后由 `openapi-typescript` 生成 DTO）

---

## 1. 工具选择

| 工具 | 能直接读 PNG | 能改文件 | 推荐 |
|---|---|---|---|
| **Claude Code（CLI / IDE）** | ✓ multimodal Read | ✓ | ★ 最佳 |
| **Cursor / Windsurf** | ✓ 附件 | ✓ | ★ 次佳 |
| Aider / Cline / Roo Code | ✓（取决于模型） | ✓ | 可用 |
| ChatGPT / Claude 网页 | ✓ 拖图但量小 | ✗ | 仅适合咨询，不适合实施 |

**Token / 模型选择**：实施这个项目建议用 Claude Sonnet 4.6+ 或 GPT-5 级别的多模态 + 长上下文模型。Haiku 4.5 适合大量轻量子任务。

---

## 2. 核心思路：四层提示词

**反模式**：一句话"根据这些文档把前端写完" → AI 一定跑偏 + 推倒重来。

**正模式**：分四层，每层独立 review：

```
L0 Bootstrap   →  喂入背景与规范索引（一次性）
L1 Scaffold    →  项目骨架 + tokens + base/* 23 个原子组件
L2 Per-Screen  →  S1..S8 每屏一个 task（建议 8 次迭代）
L3 整体 QA      →  E2E + a11y + i18n + bundle 验证
```

每层完成 + 你 review 通过 → 才进入下一层。

---

## 3. L0 Bootstrap 提示词（粘贴即用）

```
你是高级 Vue 3 前端工程师 + UI/UX 实施专家，要在 RAG-KG Copilot
项目实现完整前端（apps/web/）。先按以下顺序阅读上下文，再等我下达任务。
不要在 Bootstrap 阶段写任何代码。

## 必读规范（按顺序）
1. docs/PROJECT_OVERVIEW.md §14 前端篇
2. docs/ui-interaction-spec/UI_INTERACTIONS.md          ← 总入口 + 6 条红线
3. docs/ui-interaction-spec/FRONTEND_TECH_STACK.md     ← 库选型 + package.json + store
4. docs/ui-interaction-spec/01-tokens-input-atoms.md
5. docs/ui-interaction-spec/02-display-atoms.md
6. docs/ui-interaction-spec/03-shell-nav.md
7. docs/ui-interaction-spec/04-chat-evidence-citation.md  ← 旗舰交互
8. docs/ui-interaction-spec/05-kg-canvas.md
9. docs/ui-interaction-spec/06-docs-ingest.md
10. docs/ui-interaction-spec/07-reasoning-eval-settings.md
11. docs/ui-interaction-spec/08-screens-modals-states-journeys.md  ← 整合层
12. docs/FRONTEND_RULES.md + docs/FRONTEND_CODING_STANDARDS.md

## 设计图（90 张）
- 索引：docs/UI_GALLERY.md（如已复制进 ui-interaction-spec/ 用本地路径）
- 真图：docs/ui-images/{slug}.png
- 当我提到 "S3 / 03-I / 02-K / J2" 等编号 → 必须打开对应 PNG 仔细看

## 六条不可破红线
1. Citation-first：渲染期 whitelist 过滤 LLM 编造 `[id]`
2. Library 隔离：URL 含 :libraryId；切库 = router.push + $reset 广播
3. 长任务可后台 / 断点续 / 取消
4. Budget 是硬墙（exceeded 全 disable expensive actions）
5. A11y：aria-live 节流 ≥ 250 ms / focus stack / focus ring 3 px
6. 流断不清空（保留已输出 token + Continue from here）

## 回复要求
读完后回复"准备完毕"，并列出：
A) 你识别到的 3 个最容易出错的细节
B) 你打算用哪个包管理器（pnpm / yarn）
C) 你需要我补充的 3 个信息（如 openapi.json 在哪、是否已有 API mock、设计图是否已本地化）

不要写任何代码。
```

---

## 4. L1 Scaffold 提示词

```
执行 L1 Scaffold task。目标：项目可跑通 + 全部 base/* 原子组件就位 + 测试通过。

## 工作内容
1. 在 apps/web/ 用 Vite 5 + Vue 3.4 + TS strict 初始化
2. 按 FRONTEND_TECH_STACK.md §13 完整安装 dependencies
3. 配置 UnoCSS：把 01-tokens-input-atoms.md §1 的全部 token 注入 uno.config.ts
   - 颜色 / 间距 / 字号 / 圆角 / 阴影 / z-index / 动效
   - 暴露 CSS variable 供 Naive themeOverrides
4. 实现 components/base/* 全部原子（23 个）
   - 输入类：Button / Input / Textarea / Select / Slider / Checkbox+Radio+Toggle
   - 展示类：Card / Badge / Chip / Tag / Modal / Drawer / Tooltip / Popover /
     EmptyState / Skeleton / Toast / Avatar / Tabs / Divider / Progress / StatusPill / IconButton
5. 每个 base 组件：
   - <script setup lang="ts"> + defineProps + defineEmits + defineModel
   - 通过 Naive UI 薄包装，业务层禁止直 import naive-ui
   - 所有色值经 UnoCSS theme，禁 hex
   - Vitest 单元测试覆盖 ≥ 80%
6. 配置 ESLint @antfu/eslint-config + Stylelint，加规则禁止 hex 字面量
7. 跑通：pnpm dev / build / test / lint

## 工作方式
- 每完成一个 base 组件：贴出 props 表 + 测试结果 + 一段使用示例
- 等我说"通过"再做下一个，不要一次性产出 23 个

## 自检
□ uno.config.ts token 完整对齐 01 文档
□ 全部 base 组件无直接 hex
□ Naive UI 仅在 components/base/* 出现
□ pnpm test 全绿，覆盖率 ≥ 80%
□ pnpm i18n:check 通过（key 集合一致）
```

---

## 5. L2 Per-Screen 提示词模板

```
执行 L2-S{N} task：实现 {屏幕名}（路径：/{path}）

## 必读
- docs/ui-interaction-spec/{对应章节}.md 全部
- docs/ui-interaction-spec/08-screens-modals-states-journeys.md §S{N}
- docs/ui-images/{对应编号}-*.png 全部仔细看

## 实现范围
1. 路由 + meta + guard（libraryGuard / costGuard / unsavedChangesGuard）
2. 对应 Pinia store（{storeName}）含 actions / getters / $reset 钩子
3. 屏幕容器 ScreenName.vue + 子组件
4. 状态机：loading / data / empty / error（统一走 useAsyncResource）
5. 流式（若适用）：useSSEChat / useTaskStream / useTokenStream
6. i18n key（zh + en 同步补齐）
7. Vitest 单测 + Playwright E2E（核心路径）
8. @axe-core/playwright 扫描

## 验收前自检 10 条
□ URL query 反映可分享状态（filter / focus / depth / taskId …）
□ 切库时正确 $reset
□ Skeleton → Data / Empty / Error 用 useAsyncResource
□ 流式 aria-live ≥ 250 ms 节流，Composer/容器 aria-busy
□ 所有色值用 token，零 hex
□ 双语 key 完整通过 pnpm i18n:check
□ Playwright E2E 通过
□ axe 0 critical violation
□ 首屏 JS ≤ 300 KB gz（rollup-visualizer 截图）
□ 与对应 0X 文档的"3 条铁律"全部满足

## 工作方式
- 先贴：路由 + store 类型签名 + 关键 composable 的接口草图
- 我说"通过"再写组件实现
- 完成后贴 git diff + 测试报告
```

---

## 6. 五个具体可粘贴的 L2 prompt

### 6.1 S3 Chat（旗舰，优先做）

```
执行 L2-S3 Chat：参考 04-chat-evidence-citation.md + 08-... §S3。

## 关键交付
- 三栏 grid 260px / 1fr / 440px；<lg 折成 Tabs
- 实现 useSSEChat(sessionId) composable：解析 event: meta / token / citations / done / error
  五事件，用 @microsoft/fetch-event-source（支持 POST + Authorization）
- 实现 useTokenStream()：rAF 节流追加 + 智能 autoscroll
  （用户向上滚 ≥ 60 px 即停 autoscroll，回到底再恢复）
- CitationChip 渲染期 whitelist 过滤（chatStore.citationsIndex[msgId] 是唯一信源）
- Composer：Enter 发送 / Shift+Enter 换行 / ⌘Enter 强发 / Esc Esc 清空且存草稿
- 流断保留已输出 token + "Continue from here" / "Retry"
- markdown-it 自定义规则把 `[id]` 编译为 <CitationChip>，配 shiki 代码高亮 + katex

## 必看图
- 070-s3-chat-qa-lib-idchat.png
- 032-03-i-citationchip.png ★
- 033-03-j-evidencecard.png
- 034-03-k-evidencepanel.png
- 035-03-l-messagebubble-user-vs-assistant.png
- 037-03-n-composer.png ★
- 088-j1.png（J1 首次旅程的 chat 端）

## 工作方式
先贴：
1. useSSEChat / useTokenStream / useCitationFilter 三个 composable 的接口签名
2. chatStore / evidenceStore 类型 + actions 列表
3. CitationChip 组件的 props + emits

我说"通过"再写实现。
```

### 6.2 S4 KG

```
执行 L2-S4 KG：参考 05-kg-canvas.md。

## 关键
- Cytoscape.js + cytoscape-fcose 力导向 + cytoscape-popper + cytoscape-cxtmenu + cytoscape-edgehandles
- 节点 / 边数据走 shallowRef，cy 实例 markRaw（不让 Vue reactivity 渗入）
- 节点 > 3000 自动 lazy import sigma.js WebGL 降级
- 标签默认折叠（zoom < 0.6 隐藏）
- hover 一度邻居高亮 + 其余 opacity 30%
- URL: ?focus=...&depth=1..3&types=...&conf=0.x&q=...&zoom=...&px=...&py=...
- EntityDetailDrawer 与画布联动（kgStore.activeEntityId）

## 必看图
- 071-s4-kg-browser-lib-idkg.png
- 039-03-p-kg-canvas.png
- 040-03-q-kg-node.png
- 041-03-r-kg-edge.png
- 042-03-s-kg-filter-panel.png
- 043-03-t-entity-detail-drawer-in-kg-view.png

## 先贴
KGCanvas.vue 的 composition 结构（ref / shallowRef / markRaw / cy lifecycle 在哪个 hook），
通过后再写完整组件。
```

### 6.3 S5/S5b Review 长任务

```
执行 L2-S5/S5b Review：参考 06-docs-ingest.md §长任务 + 08-... §J2。

## 关键
- S5b 配置表单：vee-validate + zod schema（topic / sections / depth / reranker / budget）
- POST /review → taskId → router.push(/lib/:id/review/:taskId)
- useTaskStream(taskId) ：单 EventSource 按 taskId ref-count 复用
- PipelineTree + RunStatsSidebar + LiveCitationList + DraftStream 四组件共享同一流，
  从 taskStore.tasks[taskId] 投影不同视图
- "Run in background" → tasksStore 持有连接所有权，组件 unmount 不断流
- 右下角 mini progress pill
- DraftStream scrollIntoView 节流 ≥ 800 ms 居中
- server checkpoint 失败 → "Resume from section X"

## 必看图
- 073-s5b-review-configuration-pre-run.png
- 072-s5-review-generation-in-progress.png
- 048-03-y-pipeline-tree-taskprogress.png
- 049-03-z-run-stats-sidebar.png
- 050-03-aa-live-citation-list.png
- 051-03-ab-review-draft-streaming-view.png
- 089-j2.png

## 先贴
useTaskStream 实现 + ref-count GC 单测（5 个 case），通过后再做 UI。
```

### 6.4 全局外壳 + 路由

```
执行 L2-Shell：参考 03-shell-nav.md。

## 关键
- AppShell.vue：CSS Grid 锁定 [64 / sidenav-var / 1fr] × [topbar / main]
- libraryStore.$onAction 切库时广播 reset 给 chat / evidence / kg / task store
- LibrarySwitcher 三段：Search / Pinned(≤5) / Recent(LRU)
- 快捷键：⌘O 切库 / ⌘N 新建 / ⌘K cmdk / Esc 关浮层 / g d g c g k g e 跳页
- 切库时如有 dirty draft：二次确认 Modal
- 切换后 5 s Toast 提供 Undo 回滚 activeLibraryId
- 业务页禁止自建 fixed 顶/侧栏；只能 <Teleport to="#named-slot">
- useShortcut(scope) 中央 dispatcher

## 必看图
- 024-03-a-topbar.png
- 025-03-b-sidenav.png
- 027-03-d-libraryswitcher.png

## 先贴
AppShell grid + named slot 草图 + libraryStore.$onAction 实现 + useShortcut(scope) 接口，
通过后再写 UI。
```

### 6.5 M3 CommandPalette ⌘K

```
执行 M3 CmdK Overlay：参考 08-... §M3。

## 关键
- ⌘K / Ctrl+K 打开，Esc 关
- fuse.js 模糊搜索（threshold 0.3，weight: title 0.7 / desc 0.3）
- 前缀分组：entity: / doc: / task: / cmd:
- Tab 切分组、↑↓ 选项、Enter 跳、⌘↵ 在新 tab 打开（如适用）
- recent LRU 10 + suggestion 列表
- 结果 > 50 → vue-virtual-scroller 启用
- 不用 cmdk-vue（API 不稳定）→ 自封装

## 必看图
- 029-03-f-cmdk-search-trigger.png
- 079-m3-commandpaletteoverlay.png

## 先贴
useCmdK composable API（open / close / setQuery / select）+ commandPaletteStore 类型 +
fuse.js index 结构，通过后再写 Overlay UI。
```

---

## 7. L3 整体 QA 提示词

```
执行 L3 QA：

## Playwright E2E（5 条核心路径）
1. 建库 → 上传 PDF → 等摄取完成
2. 提问 → 看 citation → 跳证据
3. 生成综述 → 后台运行 → 完成 → 导出 markdown
4. KG 浏览 → 选两节点 → reason → Discuss in Chat → 反向高亮
5. 评测面板 → 看 KPI → 改 budget → 验证硬墙生效

## 自动化检查
- @axe-core/playwright 全屏扫描：critical = 0
- pnpm i18n:check 通过（key 集合一致）
- rollup-visualizer 截图：首屏 JS ≤ 300 KB gz
- pnpm test：单元测试覆盖 ≥ 80%
- pnpm typecheck：strict mode 零错误

## 输出
每项贴结果截图 / log；红色项立即修复，不修不算 L3 通过。
```

---

## 8. 喂图最佳实践

- **Claude Code / Cursor**：让 AI 用 Read 直接读 PNG，自动 vision 解析；每个 L2 任务只让它读涉及的 5–10 张图，不要塞 90 张
- **网页 AI**：一次拖入 ≤ 5 张，按屏迭代
- **不要**：把 PNG base64 inline 进 prompt（炸 context + 浪费 token）
- **如果文件夹是自包含包**：路径用 `./ui-images/...`；否则用 `docs/ui-images/...`

---

## 9. 反模式（一开就废）

| ❌ 反模式 | ✓ 正确做法 |
|---|---|
| "根据这些文档把前端写完" | 分四层，每层 review |
| 一次性塞 11 份规范 + 90 张图 | 先 Bootstrap，再 task by task |
| 让 AI 跳过 base/* 直接做屏幕 | 强制先做 L1，否则违反硬规矩 |
| 不 review 中间产物 | 每个 base / store / composable 都 review |
| 让 AI 自选库 | 强制遵循 FRONTEND_TECH_STACK.md |
| i18n 只写中文 | zh + en 同步，CI 校验 |
| 跳过 a11y 测试 | axe critical = 0 是硬指标 |
| 把生成的 OpenAPI 类型手改 | 由 openapi-typescript 重生，禁止手改 |

---

## 10. 推荐迭代节奏

| 阶段 | 时长（合作） | 关键产出 |
|---|---|---|
| L0 Bootstrap | 10 min | AI 回 "准备完毕" + 3 个潜在坑 |
| L1 Scaffold | 1 天 | 项目可跑 + 23 个 base 组件 + 测试 |
| L2 S3 Chat（先做） | 1.5 天 | useSSEChat + Composer + CitationChip 一条龙 |
| L2 S6 Docs | 1 天 | useTaskStream + DropZone + 表格 |
| L2 S4 KG | 1.5 天 | Cytoscape 集成 + Filter + EntityDrawer |
| L2 S5 Review | 1 天 | 复用 S6 useTaskStream + DraftStream |
| L2 S1 / S2 / S7 / S8 | 各 0.5–1 天 | |
| L3 QA | 1 天 | 5 条 E2E + axe + bundle + i18n |
| **合计** | **~10–12 天** | 完整前端 v1 |

⚠️ 8 屏并行 ≠ 8 倍速。**强烈建议串行**：S3（旗舰，孵化 useSSEChat / useTokenStream 基建）→ S6（孵化 useTaskStream）→ S4 → S5（复用 S6）→ S2 → S1 → S7 → S8。

---

## 11. 当 AI 卡住时的应急 prompt

```
对照 docs/ui-interaction-spec/UI_INTERACTIONS.md §7 "极易踩坑的细节" 自检：
逐条说明你的实现是否满足该条；不满足的修正。然后重新跑 E2E + axe。
```

```
你违反了硬规矩 X（如 "业务层 import 了 naive-ui"）。
查 FRONTEND_RULES.md，把违规位置全部修复，回贴 diff。
```

```
你的实现与 0X-*.md 中 {组件名} 的"3 条铁律"不一致。
逐条对比，修正后回贴。
```

---

> 本指南本身可作为 system prompt 的一部分；最简化的使用方式是把它直接粘贴到 AI 工具的"项目说明"或 system message 中。
