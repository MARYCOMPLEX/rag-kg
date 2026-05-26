# UI / UX 设计文档 — RAG-KG Copilot

**文档状态**：v0.1 / Draft
**对齐版本**：PRD v0.2（M7 — Hardening）
**最后更新**：2026-05-05
**目标读者**：前端工程师、产品、设计协作方
**配套**：`docs/PRD.md` · `docs/FRONTEND_CODING_STANDARDS.md` · `docs/openapi.json`

> 本文档定义 RAG-KG Copilot 在 v1.0 (M7) 前端形态：信息架构、设计系统、页面与组件清单、关键交互流。
> Figma 实现按本文档逐屏落地，每屏含设计稿引用 ID。

---

## 0. 设计原则

| 原则 | 含义 | 反例 |
|---|---|---|
| **Citation-first** | 任何 LLM 输出都以引用 chip 出现，点击即跳证据 | 把"答案"和"来源"分开两个 tab |
| **Library-aware** | URL/状态/视觉提示始终告诉用户「我现在在哪个 Library」 | 切了库但顶栏不变 |
| **Progressive Disclosure** | 默认极简界面，高级旋钮（reranker / planner / budget）折叠在二级菜单 | 主页面塞满设置 |
| **Long-task First-class** | 综述/批量摄取等长任务有显式进度面板，可后台、可恢复 | 转圈圈遮罩 5 分钟 |
| **Trust through Trace** | 任何答案都能展开"它是怎么得来的"（检索步骤、命中分数） | 黑箱信任 |
| **Keyboard-native** | 所有主流程支持 `⌘K` 命令面板与快捷键 | 必须用鼠标 |

---

## 1. 用户与场景重述（来自 PRD §2）

| Persona | 主要任务 | 进入路径 |
|---|---|---|
| **博士/博后**（深耕单一子方向） | 每日刷文献、写综述、追溯引用、产生新假设 | 桌面 web，长会话 |
| **小型课题组**（3–10 人） | 共享 Library、协作整理 KG、互相提问 | 同上，多用户在同 Library 并发 |

**核心场景映射 → 入口**：

| UC | 名称 | 主入口 | 二级入口 |
|---|---|---|---|
| UC0 | Library 管理 | 顶栏 LibrarySwitcher / 仪表盘 | `⌘K` → "create library" |
| UC1 | 精准问答 | Chat 主页 | `⌘K` → "ask" |
| UC2 | 实体透视 | KG Browser / Chat 中点击实体 chip | `⌘K` → "explore entity" |
| UC3 | 主题综述 | Tasks → Review | Chat 输入 `/review <topic>` |
| UC4 | 跨文献推理 | Tasks → Reasoning | Chat 输入 `/reason <q>` |
| UC5 | 假设生成 | Tasks → Hypothesize | Chat 输入 `/hypothesize <e1>,<e2>` |

---

## 2. 信息架构

```
App
├── /onboarding                # 无 Library 时的引导
├── /libraries                 # Library 仪表盘（全局首页）
│   └── /libraries/new         # 创建向导
└── /lib/:libraryId            # ★ 所有 Library-scoped 页面均挂在此前缀下
    ├── /                      # Library 概览（Stats）
    ├── /chat                  # 主 Chat / QA  ⭐ 默认入口
    │   └── /chat/:sessionId   # 会话历史
    ├── /docs                  # 文献库（列表/上传/解析进度）
    │   └── /docs/:docId       # 文献详情
    ├── /kg                    # 知识图谱浏览器
    │   └── /kg?entity=:id     # 实体详情侧栏
    ├── /review                # 综述生成
    │   └── /review/:taskId    # 综述任务进度/结果
    ├── /reason                # 跨文献推理
    │   └── /reason/:taskId
    ├── /hypothesize           # 假设生成
    │   └── /hypothesize/:taskId
    ├── /eval                  # 评测仪表板（VAR/Citation F1/P95/cost）
    └── /settings              # Library 设置（Schema/预算/导出）
└── /settings                  # 全局设置（模型/账号/通用）
```

**URL 强约束**：所有 Library-scoped 页面 URL 必含 `:libraryId`，与后端 per-Library 物理隔离对偶。切库等价于路由跳转，自动清空 store。

---

## 3. 设计系统（Design Tokens）

### 3.1 色板 — "Cobalt Lab"

**风格定位**：现代学术 SaaS（Linear × Notion × Arc Browser），蓝紫学术主调 + 高对比文本 + 克制的彩色强调。

#### 中性色（Neutrals）— 暖灰偏
| Token | Hex | 用途 |
|---|---|---|
| `bg-canvas` | `#FAFAF9` | 应用底（暖白，护眼） |
| `bg-surface` | `#FFFFFF` | 卡片 / 面板 |
| `bg-subtle` | `#F4F4F2` | hover / 二级背景 |
| `bg-muted` | `#EBEBE8` | 分隔块 |
| `border-subtle` | `#E5E5E1` | 卡片描边 |
| `border-default` | `#D4D4CE` | 输入框描边 |
| `border-strong` | `#A3A39C` | 焦点描边 |
| `text-primary` | `#1A1A1A` | 标题 / 正文 |
| `text-secondary` | `#525252` | 副标题 / 描述 |
| `text-tertiary` | `#8B8B85` | 占位 / 元数据 |
| `text-disabled` | `#BDBDB8` | 禁用 |

#### 主色（Brand）— 钴蓝紫
| Token | Hex | 用途 |
|---|---|---|
| `brand-50` | `#EEF1FF` | 浅底（chip 背景、hover） |
| `brand-100` | `#DCE3FF` | 轻强调 |
| `brand-300` | `#8DA0FF` | 渐变中段 |
| `brand-500` | `#4F46E5` | **主交互色**（按钮、链接） |
| `brand-600` | `#3B30D9` | hover |
| `brand-700` | `#2A1FB0` | active / 深色文字 |

#### 语义色（Semantic）
| 角色 | 50 | 500 | 700 |
|---|---|---|---|
| Success（绿） | `#ECFDF5` | `#10B981` | `#047857` |
| Warning（琥珀） | `#FFFBEB` | `#F59E0B` | `#B45309` |
| Danger（玫红） | `#FEF2F2` | `#EF4444` | `#B91C1C` |
| Info / Citation（青） | `#ECFEFF` | `#06B6D4` | `#0E7490` |

> **Citation chip** 专用 `info-50/500/700`，与 brand 区隔：用户一眼能区分"这是引用"与"这是按钮"。

#### KG 实体类型色（6 类，圆点 + 文字）
| 类型 | 色 |
|---|---|
| Concept | `#4F46E5`（brand） |
| Method | `#10B981`（success） |
| Dataset | `#F59E0B`（warning） |
| Metric | `#06B6D4`（info） |
| Author | `#A855F7`（purple-500） |
| Venue | `#EC4899`（pink-500） |

#### 暗色模式（v1.0 不强求，token 预留）
所有 token 提供 `*-dark` 对应键，背景反转为 `#0E0E10` / `#17171A` 系列；M7 不交付暗色版，仅在 token 文件占位。

### 3.2 字体 (Typography)

**字族**：
- UI / 正文：`Inter`，回退 `-apple-system, system-ui`
- 中文：`PingFang SC`, `Source Han Sans SC`
- 等宽（代码 / DOI / chunk_id）：`JetBrains Mono`，回退 `SFMono-Regular`

**比例（modular scale 1.125）**：

| Token | size / line-height | weight | 用例 |
|---|---|---|---|
| `display` | 40 / 48 | 600 | Onboarding 主标题 |
| `h1` | 32 / 40 | 600 | 页标题 |
| `h2` | 24 / 32 | 600 | 区块标题 |
| `h3` | 20 / 28 | 600 | 卡片标题 |
| `body-lg` | 16 / 24 | 400 | 长文 |
| `body` | 14 / 22 | 400 | 默认正文 |
| `caption` | 12 / 18 | 400 | 元数据 / 时间 |
| `mono` | 13 / 20 | 400 | chunk_id / DOI |
| `mono-sm` | 11 / 16 | 500 | 标签 / chip |

### 3.3 间距 / 网格 / 圆角 / 阴影

**间距（4px base）**：`2 / 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64`
**栅格**：12 列，gutter 24px，content max-width 1280px，左右安全边 32px
**圆角**：
- `radius-sm` 6（chip / tag）
- `radius` 10（按钮 / 输入框）
- `radius-lg` 14（卡片）
- `radius-xl` 20（模态 / 大面板）
- `radius-pill` 999（圆形按钮）

**阴影**：
- `shadow-sm`：`0 1px 2px rgba(15,15,20,.04)`
- `shadow`：`0 4px 12px rgba(15,15,20,.06)`
- `shadow-lg`：`0 12px 32px rgba(15,15,20,.10)`
- `shadow-focus`：`0 0 0 3px rgba(79,70,229,.20)`（焦点环，无障碍）

### 3.4 动效

| 场景 | 时长 | 缓动 |
|---|---|---|
| Hover / focus | 120ms | ease-out |
| 模态弹出 | 200ms | cubic-bezier(.2,.8,.2,1) |
| 页面切换 | 240ms | ease |
| 流式打字 | 22ms / token | linear（呼吸光标） |
| KG 节点过渡 | 320ms | spring |

### 3.5 图标

- 库：**Lucide**（线性 stroke 1.5，与 Inter 视觉权重一致）
- 默认尺寸 16 / 20 / 24
- 自定义 KG 类型图标：6 个 24×24 SVG（M7 出图）

---

## 4. 全局布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TopBar  (h=56)                                                          │
│  ┌─Logo─┬─LibrarySwitcher─┬─Breadcrumb──────┬─⌘K──┬─Notify─┬─Avatar─┐    │
└─────────────────────────────────────────────────────────────────────────┘
┌──────────┬──────────────────────────────────────────────────────────────┐
│ SideNav  │  Main Content                                                 │
│  (w=240) │                                                                │
│  ◆ 概览  │                                                                │
│  ◆ Chat  │                                                                │
│  ◆ 文献  │                                                                │
│  ◆ KG    │                                                                │
│  ◆ 综述  │                                                                │
│  ◆ 推理  │                                                                │
│  ◆ 假设  │                                                                │
│  ◆ 评测  │                                                                │
│  ─────   │                                                                │
│  Stats   │                                                                │
│  (mini)  │                                                                │
└──────────┴──────────────────────────────────────────────────────────────┘
```

- **TopBar** 56px 高，半透明白 + 1px 底边。LibrarySwitcher 是顶栏左侧第二个槽位，固定可见。
- **SideNav** 240px 宽，可折叠到 64px（仅图标）。底部固定一个 mini Stats 卡。
- **Main** 自适应；Chat 与 KG 页采用三列（Nav | Chat | Evidence）。

---

## 5. 核心组件清单

> 全部用 Naive UI 原子组件搭建，自定义 5 个领域组件。

### 5.1 通用（Naive UI 包装）
- `AppButton` 5 变体：Primary / Secondary / Ghost / Danger / Link
- `AppInput` / `AppTextarea` / `AppSelect`
- `AppModal` / `AppDrawer` / `AppPopover` / `AppTooltip`
- `AppBadge` / `AppTag`（含 KG 类型色）
- `AppToast`（顶部右）
- `AppCommandPalette`（`⌘K`）

### 5.2 领域组件（自定义）
1. **`LibrarySwitcher`** — 顶栏下拉，含搜索、最近、固定置顶、"+ New Library"
2. **`CitationChip`** — `[12]` 圆角 pill，hover 弹出预览（标题/作者/年份/段落首句），click → 滚动到右侧证据面板
3. **`EvidencePanel`** — 右侧 360px 抽屉，每条证据卡：标题 + 元数据 + 命中文本（高亮 query 词）+ score + source（vector/graph/bm25/community 图标）
4. **`KGCanvas`** — Cytoscape 包裹组件，顶部工具栏（深度 1/2/3 / 类型 filter / fit / 导出 PNG）
5. **`TaskProgress`** — 长任务进度面板：阶段步骤条 + 实时日志 SSE 流 + 取消/后台

---

## 6. 页面规范（Screen Specs）

### S1. Onboarding / Welcome

**触发**：`GET /v1/libraries` 返回空数组。
**目标**：30 秒内引导用户创建第一个 Library 并理解"Library 是数据分区"。

**布局**：
- 全屏单列居中，max-width 720px。
- Hero：display 字体 "Your private RAG-KG Copilot." + 副标题。
- 3 步说明卡片（横排）：① Create a Library ② Drop in your PDFs ③ Ask with citations.
- 主 CTA：`Create your first Library`（brand-500 大按钮）。
- 次 CTA：`See a demo Library`（ghost）。

**交互**：CTA → 打开 `LibraryCreateModal`。

---

### S2. Library 仪表盘（`/libraries`）

**目标**：跨 Library 总览 + 切换 + 管理。

**布局**：
- 顶部欢迎条：`Welcome back, {user}`。
- Library 网格：每个 Library 一张卡（宽 320，高 180），含：
  - Library 名 + 描述（2 行截断）
  - mini Stats: docs / chunks / entities / triples（4 个数字）
  - 状态徽章：`Healthy` / `Indexing` / `Stale community`
  - 右上 `…` 菜单：Open / Rename / Export / Delete (purge)
- 卡片末位是 dashed border 的 `+ New Library` 卡。

**交互**：
- click 卡 → `/lib/:id`
- Delete → 二次确认弹窗（输入 library_id 才能确认 purge）

---

### S3. ★ Chat / QA（`/lib/:id/chat`）— 默认入口

**布局（三列）**：

```
┌─SideNav─┬───────── Conversation Center ──────────┬── Evidence Panel ──┐
│  240    │                                        │      360            │
│         │  Session header                        │                     │
│         │  ──────────────────                    │  Currently citing:  │
│         │  user: ...                             │  [1] Vaswani 2017   │
│         │  bot:  Transformer is ... [1][2]      │  ... text excerpt   │
│         │       (streaming token cursor)         │  score 0.91 vector  │
│         │                                        │  ───────             │
│         │  ╭─Composer (sticky bottom)──╮         │  [2] Devlin 2018    │
│         │  │ Ask about this library... │         │  ...                │
│         │  │  ⌘↩ to send · /review     │         │                     │
│         │  ╰───────────────────────────╯         │                     │
└─────────┴────────────────────────────────────────┴─────────────────────┘
```

**关键细节**：
- **Message bubble**：assistant 消息无气泡，直接段落排版（Notion 风），引用 `CitationChip` 内联。
- **流式 cursor**：闪烁 brand-500 竖线 (▌)。
- **Reasoning toggle**：每条 assistant 消息底部小链接 `Show reasoning trace`，展开后显示 ReAct 步骤（thought/action/obs）。
- **Composer**：
  - 单行起步、Enter 换行、`⌘↩` 发送（按钮 hint 显式）
  - Slash 命令下拉：`/review` `/reason` `/hypothesize` `/clear` `/rerank-on`
  - 左下：当前 Library Pill（不可改，提醒上下文）+ 模型 selector（Local Qwen / Claude Haiku / GPT-4o-mini）
  - 右下：`Budget: 8 steps · 32k tok` （可点击调整）
- **Empty state**：3 个示例问题胶囊，click 自动填入 composer。
- **Right panel**：默认折叠为 56px 窄条；hover/click 展开 360px。

---

### S4. KG Browser（`/lib/:id/kg`）

**布局**：
- 左侧 280px Filter 栏：实体类型多选（6 色 chip）/ 深度滑杆 1-3 / 三元组 confidence 阈值。
- 中部画布：Cytoscape 力导向，节点圆形（大小 ∝ degree），边浅灰带箭头，hover 高亮 1-hop。
- 右侧 360px Detail 抽屉（点击节点出现）：实体卡 + 别名 + 描述 + 邻接三元组列表（可点击跳证据 chunk）+ "在 Chat 中提问该实体"按钮。
- 顶部工具栏：搜索实体 / Fit / Reset / Export PNG / Export JSON。

---

### S5. 综述生成（`/lib/:id/review`）

**两阶段单页**：

**阶段 1 — 配置**：
- 中央卡 `Generate a Review`：主题输入框（多行）、年份范围 slider、可选子主题手动添加（chip）、目标字数 选择（1500/3000/5000）、引用风格（编号/作者-年份）。
- `Estimate cost` 按钮 → 显示预计 token 数 + 美元成本 + 时长 → `Run` 按钮。

**阶段 2 — 进行中**（`/review/:taskId`）：
- 左侧 320px `TaskProgress`：步骤树
  ```
  ◉ Decompose into subtopics      (3.2s · 412 tok)
  ◉ Subtopic 1: Pre-trained models
    ◉ Local search    32 chunks
    ◉ Draft           ▌ writing...
  ○ Subtopic 2: ...
  ○ Citation cross-check
  ```
- 中部主区：实时拼装的综述 markdown 视图，引用 chip 可点。
- 右侧 320px：当前阶段命中证据。
- 底部：`Cancel` / `Run in background` / `Download .md`。

---

### S6. 文献摄取 / Documents（`/lib/:id/docs`）

**布局**：
- 顶部工具条：搜索 / 排序（日期/标题/作者）/ `+ Upload` 主按钮。
- 上传区（拖拽热区，dashed border 380px 高）：可拖入多 PDF；支持文件夹与 zip。
- 文献列表表格：cover缩略图 / 标题 / 作者 / 年份 / 解析状态徽章 / chunk 数 / 入库时间 / 操作（重解析 / 删除）。
- 状态徽章：
  - `Queued`（neutral）
  - `Parsing`（brand 进度环）
  - `Indexing`（success 进度环）
  - `Ready`（success 实心）
  - `Failed`（danger，hover 看错误，可重试）

**详情**（`/docs/:docId`）：右侧抽屉显示 PDF preview（左）+ 章节大纲 + chunk 列表（右）。

---

### S7. 跨文献推理 + 假设生成

**`/reason`**：
- 输入区类似综述，但默认 placeholder 是多跳问题（"A 团队的方法是否被 B 场景验证过？"）
- 输出区分 3 块：① 路径可视化（mini KG，meta-path 高亮）② 证据时间线 ③ 结论 + 引用

**`/hypothesize`**：
- 双实体输入（带 autocomplete from KG）+ "Find paths" 按钮。
- 候选假设列表卡：每条卡 = 假设文本 + 评分（信度/新颖性/可验证性 三条 mini bar）+ KG 路径缩略 + 证据 chunk chip。

---

### S8. 评测 + 设置

**`/eval`** 仪表盘：
- 4 张 KPI 卡：VAR · Citation F1 · P95 latency · $/query
- 4 张 ECharts：折线（30 天 VAR 趋势）/ 柱状（按问题类型）/ 散点（cost vs 长度）/ 表格（最近 10 条失败）
- 顶部 filter：评测集 selector（smoke / multihop / review）+ 时间范围。

**`/settings`** Library 设置：
- Schema YAML 编辑器（Monaco-lite）
- LLM / Embedder 路由（per-Library 覆盖全局）
- 预算（每日 / 每查询）
- 导出 / 导入按钮

---

## 7. 关键交互流（用户旅程）

### J1. 首次使用 → 第一答案

```
Visit / → Onboarding (S1)
  → Click "Create your first Library"
  → LibraryCreateModal (id slug + 名称 + 描述 + 主语言)
  → 创建成功 → /lib/:id (S3 Chat)
  → 空状态 → 顶部提示 "Upload your first PDFs"
  → Click → /lib/:id/docs (S6) → 拖入 10 PDFs
  → 解析进度（worker SSE）
  → 列表全部 Ready
  → 顶部 toast "Ready to ask. Open Chat ↗"
  → 回到 /chat
  → 输入示例问题 → 流式回答 + 引用 chips
  → 点击 [1] → 右侧 EvidencePanel 滑出
```

### J2. 综述生成长任务

```
/lib/:id/chat → 输入 "/review GraphRAG progress 2024-2025"
  → 路由到 /review 配置页（参数预填）
  → Estimate → Run
  → /review/:taskId
  → SSE 步骤树实时更新
  → 中途用户点 Run in background
  → 顶栏 Notify 出现红点
  → 完成 → 顶栏 toast → Click → 回任务页查看 + 下载 .md
```

### J3. KG 探索 → 反馈到 Chat

```
/lib/:id/kg
  → 搜索 "GraphRAG" → 节点居中
  → 点击节点 → 抽屉显示三元组
  → 点 "在 Chat 中提问" → 跳 Chat 并预填 "Tell me about GraphRAG"
```

---

## 8. 状态、加载与错误

| 场景 | 表现 |
|---|---|
| **首次加载页面** | Skeleton（脉冲动画 1.2s）；超过 800ms 才显示，否则直接出内容 |
| **流式响应中断** | 在最后一个 token 后插入红字 "Stream interrupted. Retry" 链接 |
| **检索失败 0 命中** | 不要假装回答；显式空状态卡 "No evidence found in this Library. Try widening the year filter or upload more papers." |
| **跨 Library 误访问** | 路由守卫；URL 不存在 → 跳 /libraries + toast |
| **超出预算** | Composer 上方 banner "Budget exceeded. Increase or simplify the question." |
| **Worker 离线** | 顶栏红色 dot + tooltip "Ingest worker offline. Uploads queued." |

---

## 9. 无障碍 (a11y)

- 全局对比度 ≥ WCAG AA（正文 4.5:1；大字 3:1）。
- 所有交互元素键盘可达；焦点环用 `shadow-focus` token。
- 引用 chip 提供 `aria-describedby` 指向证据文本。
- KG canvas 提供 List-mode（侧栏列表替代图，盲人用户可读）。
- 国际化：zh-CN（默认）+ en-US；所有 placeholder/error 走 i18n。

---

## 10. 性能预算

| 指标 | 目标 |
|---|---|
| FCP | ≤ 1.2s（home / chat） |
| LCP | ≤ 2.0s |
| TTI | ≤ 2.5s |
| 首屏 JS | ≤ 220 KB gzip（含 Vue + Naive UI Tree-shaken + UnoCSS） |
| KG 路由懒加载 | Cytoscape 单独 chunk，hover Nav 时 prefetch |
| 长会话内存 | 单页 < 200MB（虚拟列表 + 历史折叠） |

---

## 11. 与后端契约的对接

- DTO 由 `pnpm gen:api` 从 `/openapi.json` 生成（`docs/FRONTEND_CODING_STANDARDS.md`）。
- 关键 endpoint：
  - `POST /v1/libraries`、`GET /v1/libraries`、`DELETE /v1/libraries/{id}?purge=1`
  - `POST /v1/libraries/{id}/ingest`（multipart）
  - `POST /v1/libraries/{id}/qa`（SSE）
  - `GET /v1/libraries/{id}/entities/{eid}/neighborhood`
  - `POST /v1/libraries/{id}/review|reason|hypothesize`（SSE，长任务）
- 前端**不**自定义 citation 结构，完全信任 `citations[]`。

---

## 12. Figma 文件结构（实现指引）

Figma 单文件，所有 Frame 在同一 Page，按以下网格平铺：

```
Row 0  (y = 0):    Cover (1440×400)
Row 1  (y = 480):  Design Tokens — Color · Type · Spacing · Shadow · Iconography
Row 2  (y = 1880): S1 Onboarding             |  S2 Library Dashboard
Row 3  (y = 2880): S3 Chat (★ flagship)      |  S4 KG Browser
Row 4  (y = 3880): S5 Review Progress        |  S6 Documents
Row 5  (y = 4880): S7 Reason / Hypothesize   |  S8 Eval + Settings
```

Frame 命名规范：`[Sn] <ScreenName> — Desktop 1440`。
所有 Frame 1440×900（除 Tokens 区域）。
Auto-layout 默认 vertical 24px gap，padding 32px。

---

## 13. 验收清单（M7 Exit Criteria 对齐）

- [ ] 8 个 Screen 全部完成 Figma 高保真稿
- [ ] Design Tokens Frame 含 5 类全部色板与示例
- [ ] 关键流程 J1 / J2 / J3 在 Figma 内通过 connector 串联
- [ ] 5 位目标用户 α 测试，VAR ≥ 70%（运行时验证，不是设计稿）
- [ ] Lighthouse: Performance ≥ 85, Accessibility ≥ 95（运行时）
- [ ] 与 `FRONTEND_CODING_STANDARDS.md` 完全一致

---

**END**
