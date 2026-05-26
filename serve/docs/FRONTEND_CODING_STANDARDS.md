# 前端代码规范与工程约定（Vue 3）

本文档是 **RAG-KG Copilot** 项目的**前端代码规范与工程约定**。所有参与者（含 AI 协作）必须遵循。本文与 `CODING_STANDARDS.md`（后端 Python 规范）**对偶**：相同的接口先行、模块化、可测试原则，落到 Vue/TS 生态。

> 底层准则：**契约先于 UI；组件即接口；类型与后端同源**。

---

## 目录

1. [定位与边界](#1-定位与边界)
2. [语言与工具链](#2-语言与工具链)
3. [仓库与目录结构](#3-仓库与目录结构)
4. [依赖方向与架构边界](#4-依赖方向与架构边界)
5. [命名约定](#5-命名约定)
6. [TypeScript 类型系统](#6-typescript-类型系统)
7. [不可变性与数据建模](#7-不可变性与数据建模)
8. [API 客户端：与后端契约同源](#8-api-客户端与后端契约同源)
9. [状态管理（Pinia）](#9-状态管理pinia)
10. [组件设计](#10-组件设计)
11. [Composables（可复用逻辑）](#11-composables可复用逻辑)
12. [路由](#12-路由)
13. [错误处理](#13-错误处理)
14. [异步与并发（含 SSE 流式）](#14-异步与并发含-sse-流式)
15. [Library 隔离原则（与后端对齐）](#15-library-隔离原则与后端对齐)
16. [引用与 KG 可视化](#16-引用与-kg-可视化)
17. [样式与 UI 一致性](#17-样式与-ui-一致性)
18. [国际化（i18n）](#18-国际化i18n)
19. [可观测性](#19-可观测性)
20. [安全与权限](#20-安全与权限)
21. [测试规范](#21-测试规范)
22. [性能与可访问性](#22-性能与可访问性)
23. [依赖管理](#23-依赖管理)
24. [代码审查清单](#24-代码审查清单)
25. [CI/CD 红线](#25-cicd-红线)

---

## 1. 定位与边界

- 前端是**展示层**：所有业务规则、检索策略、引用规则都在后端。前端**只**负责契约调用、状态管理、可视化。
- 前端**不感知**底层 LLM、向量库、KG 后端选型。任何"哪个模型/哪个索引"的字段必须由后端 API 显式返回，前端透传。
- 前端**不缓存**业务推断（例如：不在客户端做"我猜这个查询应该用 global"），路由决策永远来自后端 `/v1/.../route` 之类的端点。

---

## 2. 语言与工具链

### 2.1 基线版本

| 项 | 版本 | 说明 |
|---|---|---|
| Node.js | **20 LTS+** | 锁定到 LTS，CI/CD 与本地一致 |
| 包管理 | **pnpm** | 禁止混用 npm/yarn；锁文件 `pnpm-lock.yaml` |
| 框架 | **Vue 3.4+** | 仅 Composition API + `<script setup>` |
| 构建 | **Vite 5+** | 禁止 webpack |
| 语言 | **TypeScript 5.4+ strict** | `strict: true`，等价后端 pyright strict |
| 路由 | **Vue Router 4** | |
| 状态 | **Pinia** | 禁用 Vuex |
| UI 库 | **Naive UI** | TS 原生、无 SCSS 依赖；按需引入 |
| 原子 CSS | **UnoCSS** | 禁止全局 CSS 文件，除主题变量外 |
| HTTP | **openapi-fetch** + 自动生成的 OpenAPI 类型 | 禁止手写 DTO |
| 类型生成 | **openapi-typescript** | 由 FastAPI `/openapi.json` 自动生成 |
| Linter | **ESLint 9 flat config** + `@vue/eslint-config-typescript` | |
| Formatter | **Prettier 3** | 与 ESLint 通过 `eslint-config-prettier` 解耦 |
| 单测 | **Vitest** | 与 Vite 同源，jsdom env |
| 组件测试 | **@vue/test-utils** + **@testing-library/vue** | |
| E2E | **Playwright** | 配合 backend 起来跑，禁止 Cypress |
| 图表 | **ECharts** | Stats 面板 |
| 图谱 | **Cytoscape.js** | KG 浏览器（PRD 指定） |
| Markdown | **markdown-it** + **shiki** | 渲染 LLM 输出 + 代码高亮 |
| i18n | **vue-i18n@9** | zh-CN / en-US |
| 日期 | **date-fns** | 禁止 moment |

### 2.2 工具锁定

- 工具版本通过 `pnpm-lock.yaml` 锁定；CI 使用 `pnpm install --frozen-lockfile`。
- ESLint / Prettier / TS 配置集中在 `apps/web/` 根，**禁止**子目录覆盖。
- 任何新依赖进入 `package.json` 之前需写 1 行理由到 PR 描述（与后端 ADR 对应，但门槛更低）。

---

## 3. 仓库与目录结构

### 3.1 Monorepo 中的位置

```
research-agent/
├── apps/
│   ├── api/              # FastAPI（已存在）
│   ├── worker/           # Arq worker
│   ├── cli/              # Typer CLI
│   └── web/              # ⬅ 本文管辖
└── packages/             # 后端领域模块
```

### 3.2 `apps/web/` 骨架

```
apps/web/
├── public/                    # 静态资源（favicon 等）
├── src/
│   ├── api/                   # OpenAPI 客户端 + 薄包装
│   │   ├── generated/         # 由 openapi-typescript 生成（git 跟踪，禁止手改）
│   │   ├── client.ts          # openapi-fetch 实例 + 拦截器
│   │   └── endpoints/         # 按后端路由分组的薄包装
│   ├── stores/                # Pinia store（每个文件 = 一个 store）
│   ├── composables/           # 可复用逻辑（use*）
│   ├── components/            # 通用组件（PascalCase）
│   │   ├── library/           # Library 切换器、创建对话框
│   │   ├── chat/              # Chat / SSE / 引用
│   │   ├── kg/                # KG 浏览器（cytoscape 包装）
│   │   └── common/            # 按钮、空态、错误边界
│   ├── views/                 # 路由级页面（与组件分离）
│   ├── router/                # Vue Router
│   ├── types/                 # 领域类型（与后端 packages/core/models.py 对齐）
│   ├── utils/                 # 纯函数工具（无 Vue 依赖）
│   ├── i18n/                  # zh-CN.json / en-US.json
│   ├── styles/                # 主题变量、UnoCSS 预设
│   ├── App.vue
│   └── main.ts
├── tests/
│   ├── unit/                  # Vitest 单测（与 src/ 镜像）
│   └── e2e/                   # Playwright
├── index.html
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── vite.config.ts
├── uno.config.ts
├── eslint.config.js
└── playwright.config.ts
```

### 3.3 文件与模块尺寸

| 类型 | 软上限 | 硬上限 |
|---|---|---|
| `.vue` 单文件组件 | 200 行 | 350 行 |
| `.ts` 模块 | 200 行 | 400 行 |
| 单个函数 | 30 行 | 50 行 |
| 模板嵌套层级 | 4 | 5 |

> 超过软上限：必须能说出"为什么不能拆"。  
> 超过硬上限：CI 必须 fail（通过 ESLint 自定义规则或 file-line-count plugin）。

### 3.4 每个组件目录的标准结构

```
components/chat/
├── index.ts          # 公开导出（barrel）
├── ChatPanel.vue
├── ChatMessage.vue
├── CitationChip.vue
└── __tests__/
    └── ChatMessage.spec.ts
```

---

## 4. 依赖方向与架构边界

```
views ──▶ components ──▶ composables ──▶ stores ──▶ api/endpoints ──▶ api/client
                                          ▲
                                          └─ utils（纯函数，零依赖）
```

**硬规则**：
- `components/` **禁止**直接 import `api/`：必须经 `composables/` 或 `stores/`。
- `stores/` **禁止** import `components/` 或 `views/`（反向依赖）。
- `utils/` **禁止** import 任何 Vue / Pinia / Naive UI（保持纯函数）。
- `types/` **禁止** import 实现，只允许从 `api/generated/` 派生。

CI 通过 ESLint `import/no-restricted-paths` 强制以上边界。

---

## 5. 命名约定

| 项 | 规范 | 示例 |
|---|---|---|
| 组件文件 | PascalCase `.vue` | `ChatMessage.vue`, `LibrarySwitcher.vue` |
| Composable 文件 | camelCase 以 `use` 开头 | `useLibraryId.ts`, `useStream.ts` |
| Store 文件 | camelCase 以领域名结尾 | `librariesStore.ts`, `qaStore.ts` |
| 类型 / interface | PascalCase | `Library`, `RetrievedEvidence` |
| 常量 | SCREAMING_SNAKE_CASE | `MAX_CONTEXT_CHUNKS`, `SSE_TIMEOUT_MS` |
| 变量 / 函数 | camelCase | `fetchLibraries`, `currentLibraryId` |
| 布尔 | `is/has/should/can` 前缀 | `isStreaming`, `hasCitations` |
| 事件（emit） | kebab-case + 动词 | `update:library`, `submit-question` |
| Props | camelCase（模板 kebab-case） | `libraryId` → `library-id` |
| CSS class | UnoCSS 原子类，自定义类 kebab-case | `chat-message__body` |

**禁止**：缩写（`btn`, `cfg`, `usr`），单字母变量（除非循环索引），中文标识符。

---

## 6. TypeScript 类型系统

### 6.1 硬要求

- `tsconfig.json` 强制：
  ```json
  "strict": true,
  "noUncheckedIndexedAccess": true,
  "noImplicitOverride": true,
  "exactOptionalPropertyTypes": true,
  "noFallthroughCasesInSwitch": true,
  "verbatimModuleSyntax": true
  ```
- **禁止 `any`**。需要逃生口时用 `unknown` + 类型守卫。例外仅限第三方库 typing 缺失，必须加 `// eslint-disable-next-line` + 1 行理由。
- **禁止 `as` 断言**（除以下场景）：DOM `querySelector` / openapi 路径常量 / 测试构造夹具。其他场合用类型守卫或 schema 校验。
- 公共 API（导出函数 / 组件 props / store actions）**必须**显式标注返回类型。

### 6.2 现代写法

```ts
// ✅ 用 type / interface 区分意图
//   - interface：对象形态契约（可被实现 / 扩展）
//   - type：联合 / 映射 / 工具类型
interface Library { id: string; name: string }
type LibraryStatus = 'active' | 'archived'

// ✅ 不可变 readonly
function pickIds(libraries: readonly Library[]): readonly string[] {
  return libraries.map(l => l.id)
}

// ✅ 满足模式（satisfies）
const themes = {
  light: { bg: '#fff' },
  dark: { bg: '#000' },
} satisfies Record<string, { bg: string }>
```

### 6.3 禁止

- `any`、`Function`、`Object` 类型。
- 隐式 `any`（CI 拒绝）。
- `// @ts-ignore`（用 `// @ts-expect-error <reason>`，且必须移除时 CI 报错）。
- 类型与运行时脱节：所有跨边界数据（API 响应、URL 参数、`localStorage`）必须经 schema 校验或来自生成类型。

---

## 7. 不可变性与数据建模

### 7.1 原则

- 与后端 `frozen=True` 对偶：**所有数据对象视为不可变**。
- 禁止直接 `obj.field = x`。修改 Pinia state 必须通过 action，且使用展开运算符创建新对象：
  ```ts
  // ✅
  this.libraries = [...this.libraries, newLibrary]
  // ❌
  this.libraries.push(newLibrary)
  ```
- 计算派生数据用 `computed` / `getters`，**禁止**在多个地方重复派生。

### 7.2 集合不可变

- 所有传入组件的数组 / 对象都标 `readonly`。
- 修改前先复制：`const next = [...current]; next[0] = ...`。

### 7.3 与 Library 数据分区

- 所有 store state 必须按 `libraryId` 分桶（见第 15 节）。

---

## 8. API 客户端：与后端契约同源

### 8.1 单一事实源

- `pnpm gen:api` 调用 `openapi-typescript http://localhost:8000/openapi.json -o src/api/generated/schema.d.ts`。
- 类型文件**必须**入库，但**禁止**手改；CI 跑 `pnpm gen:api && git diff --exit-code`。
- 客户端用 `openapi-fetch`：路径与方法都被 schema 约束，**类型不匹配编译失败**。

### 8.2 端点包装

```
src/api/endpoints/libraries.ts   ← 对应 packages/.../routes/libraries.py
src/api/endpoints/qa.ts          ← 对应 QA Task 暴露端点
src/api/endpoints/kg.ts
```

每个包装器只做一件事：调用客户端 + 把 `Result | Error` 标准化。**禁止**在端点层做 UI 提示、状态写入。

### 8.3 错误信封

后端统一错误信封 `{ code, message, request_id }`；前端 `client.ts` 拦截器统一抛 `ApiError`，UI 层只 `catch` 这一个类。

---

## 9. 状态管理（Pinia）

### 9.1 Store 即领域

- 一个领域 = 一个 store：`librariesStore`、`qaStore`、`kgStore`、`evalStore`、`authStore`。
- **禁止** "godStore"。如果一个 store 文件超过 200 行，必须拆。

### 9.2 Setup 风格

```ts
export const useLibrariesStore = defineStore('libraries', () => {
  const items = ref<readonly Library[]>([])
  const currentId = ref<string | null>(null)

  const current = computed(() =>
    items.value.find(l => l.id === currentId.value) ?? null
  )

  async function refresh(): Promise<void> {
    const res = await listLibraries()
    items.value = res
  }

  return { items, currentId, current, refresh }
})
```

### 9.3 硬规则

- State 字段只读对外暴露：组件不能直接赋值 store state，必须通过 action。
- Store **禁止** import 其他 store（避免循环）。需要协同时由 composable 编排。
- 所有异步 action 返回 `Promise<void>` 或 `Promise<Result>`，**禁止**吞错；错误向上抛。

### 9.4 持久化

- 仅 `currentLibraryId` / `theme` / `locale` 持久化（`pinia-plugin-persistedstate`）；任何**业务数据**（QA 历史、KG 缓存）永远从后端取，**禁止** localStorage 缓存业务结果。

---

## 10. 组件设计

### 10.1 单一职责

- 一个组件做一件事；超过两个 `v-if` 大分支说明该拆。
- **容器 vs 展示**：
  - **View / Container**：负责调 store / composable，传数据给子组件。
  - **Presentational**：纯输入输出，**禁止**直接调 store。

### 10.2 Props / Emits

- 全部用 `defineProps<{}>()` + `defineEmits<{}>()` 类型签名（不要运行时声明）。
- Props 必须有显式默认值（用 `withDefaults`）。
- 修改父级状态用 `defineEmits` + `update:xxx`（v-model 协议），**禁止**直接 mutate prop。

### 10.3 模板

- 单根元素强制（除非用 `<template>` Fragment）。
- `v-for` 必须 `:key`，且 key 必须稳定唯一（业务 id，不用 index）。
- `v-if` / `v-else-if` 链超过 3 个 → 抽 computed 或子组件。
- 模板嵌套 ≤ 4 层。

### 10.4 样式

- 优先 UnoCSS 原子类。
- 必须自定义时用 `<style scoped>`，**禁止**全局样式（除主题变量）。
- **禁止**内联 `style="..."` 除动态计算（如 cytoscape 节点位置）。

---

## 11. Composables（可复用逻辑）

### 11.1 何时抽

- 同一段 `ref + watch + 异步` 在 ≥ 2 个组件出现 → 抽 composable。
- 跨组件共享的副作用（监听 SSE、定时器、键盘事件）→ composable。

### 11.2 命名与签名

```ts
// ✅
export function useLibraryStream(libraryId: Ref<string>): {
  events: Readonly<Ref<readonly StreamEvent[]>>
  isStreaming: Readonly<Ref<boolean>>
  start: () => void
  stop: () => void
}
```

- 名字以 `use` 开头。
- 返回对象字段都标 `Readonly<Ref<...>>`，不要把内部 `ref` 直接暴露成可写。
- 必须处理生命周期（`onScopeDispose`）：composable **不允许**泄漏 listener / interval。

---

## 12. 路由

- 路由表集中在 `src/router/index.ts`，按视图分组。
- 所有路由必须有 `meta.title`（用于浏览器标题 + i18n key）。
- 需要 Library 上下文的路由必须经 `beforeEnter` 守卫确认 `currentLibraryId` 已设置；否则跳转 Library 选择页。
- **禁止**路由参数携带敏感信息（token / 内部 id 不暴露在 URL）。

---

## 13. 错误处理

### 13.1 异常层次

```ts
// src/api/errors.ts
export class ApiError extends Error {
  constructor(public code: string, public requestId: string, message: string) { super(message) }
}
export class NetworkError extends ApiError {}
export class ValidationError extends ApiError {}
export class AuthError extends ApiError {}
```

### 13.2 原则

- **禁止**裸 `throw new Error('...')`：必须用上面的层次或 `cause`。
- **禁止**空 `catch (e) {}`：要么处理，要么向上抛，要么至少 `logger.warn`。
- UI 边界（页面 / 模态框根）必须有 `<ErrorBoundary>` 兜底；显示 `ApiError.requestId` 方便对照后端日志。

### 13.3 用户提示

- 错误提示必须：1）人话；2）含 request_id；3）给"重试"或"复制错误信息"按钮。

---

## 14. 异步与并发（含 SSE 流式）

### 14.1 取消与超时

- 所有 `fetch` 必须接受 `AbortSignal`；组件卸载时取消。
- `useStream` composable 必须在 `onScopeDispose` 中关闭 `EventSource`。

### 14.2 并发

- 顺序无关的请求并行（`Promise.all`），**禁止**串行等待；但要尊重后端速率限制（用 `p-limit`）。
- 使用 SWR-like 模式（`@tanstack/vue-query` 可选）：相同 key 的请求去重。

### 14.3 SSE / 流式

- 流式响应统一走 `useSSE(url, { onMessage, onError })`，**禁止**在组件里直接 `new EventSource`。
- 流式期间必须显示 `isStreaming` 状态 + 取消按钮。
- 网络断开必须重连（指数退避，最多 5 次），重连失败提示用户。

---

## 15. Library 隔离原则（与后端对齐）

后端的 **per-Library 物理隔离**必须在前端复刻为**逻辑隔离**：

- 所有 API 调用必须带 `libraryId`，由 `client.ts` 拦截器自动注入（从 `librariesStore.currentId`）；端点函数**不许**接受可选 `libraryId`。
- 切换 Library 必须**清空**与 Library 强相关的 store（`qaStore.history`、`kgStore.graph`、`evalStore.runs`），等价后端"换 collection"。
- 路由必须在 URL 中带 `:libraryId`（如 `/libraries/:libraryId/qa`），刷新页面能恢复上下文。
- 任何展示文字（页面标题、面包屑）必须显示当前 Library 名，避免误操作。

---

## 16. 引用与 KG 可视化

### 16.1 引用（Citation）

- LLM 答案中所有形如 `[chunk_id]` 的标记必须解析为可点击 Chip，跳到原文 / 章节。
- **禁止**前端伪造引用：渲染只信任后端返回的 `citations: Citation[]`，正则提取仅用作高亮，不作为权威来源。
- 引用 UI 必须显示：chunk_id（短哈希）、doc 标题、page、200 字节预览。

### 16.2 KG 浏览器

- 用 Cytoscape.js + `dagre` / `cose` 布局。
- 默认只渲染 top-N（N=50）邻居 + 提供过滤；**禁止**一次性 load 全图（会卡死浏览器）。
- 节点颜色按实体类型（与后端 `KGSchema` 对齐，schema 通过 API 拉取，**禁止**前端硬编码类型表）。
- 边权重 → 线宽（log scale，避免极端值）。
- 点击节点展开邻居走 `/v1/.../graph/neighbors?entity=...&depth=1`。

---

## 17. 样式与 UI 一致性

- **设计 token**集中在 `src/styles/tokens.ts`：颜色、间距、圆角、阴影、字号；UnoCSS 主题与 Naive UI 主题都从 token 派生。
- 浅色 + 深色双主题，跟随系统偏好（`prefers-color-scheme`）。
- 间距 4 / 8 / 12 / 16 / 24 / 32 px，**禁止**奇数像素。
- 文案优先 i18n key，**禁止**硬编码中文/英文字符串到组件（除 dev-only 调试）。

---

## 18. 国际化（i18n）

- 默认 zh-CN，可切 en-US。
- 所有可见文本经 `t('namespace.key')`；命名空间按 view / 组件分组。
- 日期 / 数字格式经 `vue-i18n` 的 `n` / `d`。
- 新增中文文案必须同时新增英文（CI 校验 zh-CN 与 en-US key 集合一致）。

---

## 19. 可观测性

### 19.1 前端日志

- `src/utils/logger.ts` 包装 `console`，dev 显示，prod 上报到后端 `/v1/logs`（带 sample rate）。
- **禁止**裸 `console.log`（ESLint 规则 `no-console: ['error', { allow: ['warn', 'error'] }]`）。

### 19.2 用户行为埋点

- 关键操作（创建 Library / 提问 / 查看引用 / 导出）必须埋点：`logger.event('qa.submit', { libraryId, planner })`。
- **禁止**收集 PII；**禁止**传任何 token / 密钥。

### 19.3 与后端 trace 串联

- 每个请求由 `client.ts` 注入 `X-Request-Id`（`crypto.randomUUID()`）；后端在响应回传 `X-Trace-Id`。
- 错误展示时同时给用户 `request_id` 和 `trace_id`，方便定位。

---

## 20. 安全与权限

- **禁止**把任何密钥（OpenAI key、Langfuse key 等）打进前端 bundle。前端**永远**只调后端，密钥后端持有。
- 认证用 Cookie（HttpOnly + SameSite=Lax）或 Authorization header；CSRF 保护开启。
- 用户内容渲染**必须**经 `markdown-it` + sanitize（`DOMPurify`），**禁止** `v-html` 直渲染未净化字符串。
- 文件上传（PDF）：前端校验 MIME + 大小（≤ 50 MB），后端再次校验。
- 路由级权限：`router.beforeEach` 校验 token 有效；过期跳登录页。

---

## 21. 测试规范

### 21.1 测试金字塔

| 层 | 工具 | 覆盖率目标 | 跑在 |
|---|---|---|---|
| 单测（utils / composables） | Vitest | **≥ 80%** | 每次提交 |
| 组件测试 | Vitest + @vue/test-utils | 关键组件 100% | 每次提交 |
| E2E（用户旅程） | Playwright | 5 个关键流程 | 每次 PR |

### 21.2 命名

- 测试文件 `*.spec.ts` / `*.spec.vue.ts`，与被测文件同目录的 `__tests__/`。
- 测试名 AAA：`it('returns empty list when library has no documents', ...)`。

### 21.3 原则

- **禁止**网络请求：用 MSW（Mock Service Worker）拦截，fixture 来自后端 OpenAPI schema。
- **禁止**测内部实现：测**组件契约**（props 进 / emits 出 / DOM 表现）。
- 异步测试必须 `await`，禁止 `setTimeout` 等待（用 `vi.useFakeTimers` 或 `await flushPromises()`）。

### 21.4 E2E 必跑用例（与 PRD D7.1 对齐）

1. 新用户创建 Library → 上传 PDF → 看到 "Ingestion complete"
2. 切换 Library → 提问 → 看到答案 + 至少 1 个引用 chip → 点击 chip 跳到原文
3. 打开 KG 浏览器 → 点节点展开邻居 → 节点 ≤ 50
4. 切语言 zh ↔ en → 所有可见文字切换
5. 后端 503 → 显示带 request_id 的错误 + 重试按钮工作

---

## 22. 性能与可访问性

### 22.1 性能预算

| 指标 | 阈值 | 工具 |
|---|---|---|
| 初始 JS bundle (gzip) | ≤ 250 KB | `vite-bundle-visualizer` |
| LCP | ≤ 2.5 s | Lighthouse CI |
| TTI | ≤ 3.5 s | Lighthouse CI |
| 单组件初次渲染 | ≤ 50 ms | Vue DevTools profiler |

### 22.2 优化手段

- 路由级懒加载：`() => import('@/views/QAView.vue')`。
- KG 浏览器、Cytoscape、ECharts **必须**懒加载（按需）。
- 大列表（≥ 100 项）用 `vue-virtual-scroller`。
- 图片懒加载 + WebP 优先。

### 22.3 可访问性（A11y）

- 所有可点击元素是 `<button>` 或带 `role="button"` + 键盘可达。
- 颜色对比 ≥ WCAG AA。
- 表单控件必须有 `<label>` 或 `aria-label`。
- 错误提示必须 `aria-live="polite"` 或 `assertive`。

---

## 23. 依赖管理

- 新增依赖需在 PR 中说明：用途 / 替代方案 / bundle size 增量（用 `pnpm why` + `bundlephobia` 数据）。
- **禁止**重复造轮子：日期、深拷贝、防抖节流优先用 `date-fns` / `lodash-es`（按需 import）/ `@vueuse/core`。
- **禁止**全量 import 大库（`import _ from 'lodash'`）；必须按需 `import debounce from 'lodash-es/debounce'`。
- 升级策略：每月跑 `pnpm outdated`，semver patch / minor 自动 PR；major 走 ADR-lite 评审。

---

## 24. 代码审查清单

提 PR 前自查：

- [ ] `pnpm typecheck`（pyright 等价）零错
- [ ] `pnpm lint` 零错零警告
- [ ] `pnpm test` 全绿，覆盖率 ≥ 80%
- [ ] `pnpm build` 成功，bundle 在预算内
- [ ] 新增/修改组件 ≤ 350 行；新增函数 ≤ 50 行
- [ ] 没有 `any` / `// @ts-ignore` / `console.log`
- [ ] 没有硬编码文案（i18n key 已新增）
- [ ] 所有 API 调用经生成的客户端，未手写 fetch
- [ ] 所有跨 Library 风险（store 残留）已清理
- [ ] 引用 chip / KG 节点的数据来自后端
- [ ] 新组件有 a11y 标签
- [ ] 文档：复杂组件在 `__tests__/` 旁有 README 或 storybook（如启用）

---

## 25. CI/CD 红线

CI 上以下任一失败 = block merge：

1. `pnpm install --frozen-lockfile`
2. `pnpm gen:api && git diff --exit-code src/api/generated/`（OpenAPI 类型未同步）
3. `pnpm typecheck`
4. `pnpm lint`
5. `pnpm test --coverage` 且覆盖率 ≥ 80%
6. `pnpm build`（含 bundle size check）
7. `pnpm e2e`（在 docker compose 起后端环境后跑）
8. Lighthouse CI 性能预算
9. `pnpm audit --prod` 零高危

`main` 分支保护：必须有 1 个 `code-reviewer` agent 通过 + 1 人工 review。

---

## 附：与后端规范的对齐表

| 后端规范 | 前端对偶 |
|---|---|
| pyright strict | TypeScript strict + `noUncheckedIndexedAccess` |
| Pydantic `frozen=True, extra='forbid'` | `readonly` 类型 + openapi-typescript 生成 |
| Protocol（接口先于实现） | TypeScript `interface` + composable 签名先行 |
| Repository 模式 | `api/endpoints/*` 包装 + Pinia store |
| Library 物理隔离 | URL `:libraryId` + store 切换清空 + client 拦截器注入 |
| Citation 必须来自检索证据 | 引用 chip 只信任 `citations[]`，不前端伪造 |
| 结构化日志 + trace_id | logger + `X-Request-Id` / `X-Trace-Id` 头 |
| 80% 测试覆盖 | Vitest 80% + Playwright 5 关键流程 |
| 文件 ≤ 800 行 / 函数 ≤ 50 行 | `.vue` ≤ 350 行 / 函数 ≤ 50 行 |

---

**本文档由 M7 启动时确立。任何修改必须通过 PR 评审。**
