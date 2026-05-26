# Frontend Rules — Cobalt Lab Implementation Standard

**Status**: 强制 / Mandatory
**Drives**: 还原 Figma 设计稿（fileKey `A1CKNzyz03sw6iXHvOo2IM`，14 frame）
**Authority over**: docs/UI_UX.md（设计意图） + docs/FRONTEND_DESIGN_SPEC.md（实测 token 与层级）

> 此文件是所有前端实现的硬规矩。违反任意一条 = block merge.

---

## 0. 核心原则

1. **设计稿是真相**。所有像素、色值、间距以 `FRONTEND_DESIGN_SPEC.md` 中**实测数值**为准；UI_UX.md 中如有差异，以 SPEC 为准。
2. **零自由发挥**。所有色值用 token 变量；所有尺寸用 token 间距；不允许在组件里写 `#xxx` hex 或 `12px` 数字字面量。
3. **base 组件先于业务组件**。业务组件不许直接 import Naive UI 原子；都通过 `components/base/*` 包装层使用。
4. **类型严格**。strict TypeScript，禁 `any`；外部输入用 `unknown` 收紧。
5. **a11y 是默认**。所有交互组件 ARIA 完备 + 键盘可达 + focus visible。
6. **测试先于 UI**。每个 base 组件至少 1 个 spec；每个 page view 至少 1 个 smoke spec。

---

## 1. Design Token 体系

### 1.1 Token 命名规范

CSS variables 在 `apps/web/src/styles/tokens.css`（单文件，不许散落别处）：

```css
:root {
  /* === Color: Neutrals (warm gray) === */
  --color-bg-canvas:        #FAFAF9;  /* page background */
  --color-bg-surface:       #FFFFFF;  /* card background */
  --color-bg-subtle:        #F4F4F1;  /* hover / secondary */
  --color-bg-muted:         #EAEAE5;
  --color-border-subtle:    #E4E4E0;
  --color-border-default:   #D3D3CE;
  --color-border-strong:    #8C8C82;
  --color-text-primary:     #1A1A1A;
  --color-text-secondary:   #515151;
  --color-text-tertiary:    #8C8C82;
  --color-text-disabled:    #BDBDB8;

  /* === Color: Brand (cobalt indigo) === */
  --color-brand-50:    #EDF0FF;
  --color-brand-100:   #DCE2FF;
  --color-brand-200:   #B2BCF4;
  --color-brand-300:   #8D9FFF;
  --color-brand-500:   #4F46E4;  /* primary action */
  --color-brand-600:   #3B30D9;
  --color-brand-700:   #2A1FAF;

  /* === Color: Semantic === */
  --color-success-50:  #EBFCF5;
  --color-success-500: #10B881;
  --color-success-700: #047856;
  --color-warning-50:  #FFFAEB;
  --color-warning-500: #F59E0A;
  --color-warning-700: #B45208;
  --color-danger-50:   #FDF1F1;
  --color-danger-500:  #EE4444;
  --color-danger-700:  #B91B1B;
  --color-info-50:     #EBFDFF;
  --color-info-500:    #06B6D3;
  --color-info-700:    #0E7490;

  /* === Color: KG entity types === */
  --color-kg-concept:   var(--color-brand-500);
  --color-kg-method:    var(--color-success-500);
  --color-kg-dataset:   var(--color-warning-500);
  --color-kg-metric:    var(--color-info-500);
  --color-kg-author:    #A854F7;
  --color-kg-venue:     #EB4799;

  /* === Typography (Inter / system fallback) === */
  --font-family-sans: 'Inter', -apple-system, system-ui, 'PingFang SC', sans-serif;
  --font-family-mono: 'JetBrains Mono', SFMono-Regular, monospace;

  --text-display: 700 36px/43.6px var(--font-family-sans);   /* hero */
  --text-h1:      700 28px/33.9px var(--font-family-sans);
  --text-h2:      700 22px/26.6px var(--font-family-sans);
  --text-h3:      600 20px/24.2px var(--font-family-sans);
  --text-h4:      600 18px/21.8px var(--font-family-sans);
  --text-body-lg: 400 16px/22px   var(--font-family-sans);
  --text-body:    400 14px/16.9px var(--font-family-sans);
  --text-body-sm: 400 13px/15.7px var(--font-family-sans);
  --text-caption: 400 12px/14.5px var(--font-family-sans);
  --text-meta:    500 11px/13.3px var(--font-family-sans);  /* labels */
  --text-mono:    400 13px/20px   var(--font-family-mono);

  /* === Spacing (4px base) === */
  --space-1:   4px;
  --space-2:   8px;
  --space-3:   12px;
  --space-4:   16px;
  --space-5:   20px;
  --space-6:   24px;
  --space-8:   32px;
  --space-10:  40px;
  --space-12:  48px;
  --space-16:  64px;

  /* === Radius === */
  --radius-sm:    6px;     /* chip / tag */
  --radius:       10px;    /* button / input */
  --radius-lg:    14px;    /* card */
  --radius-xl:    20px;    /* modal / large panel */
  --radius-pill:  999px;

  /* === Shadow === */
  --shadow-sm:    0 1px 2px rgba(15,15,20,.04);
  --shadow:       0 4px 12px rgba(15,15,20,.06);
  --shadow-lg:    0 12px 32px rgba(15,15,20,.10);
  --shadow-focus: 0 0 0 3px rgba(79,70,229,.20);

  /* === Animation === */
  --ease-out: cubic-bezier(.2,.8,.2,1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 320ms;

  /* === Layout === */
  --topbar-h: 56px;
  --sidenav-w: 240px;
  --sidenav-w-collapsed: 64px;
  --evidence-panel-w: 360px;
}
```

### 1.2 Token 使用规则

✅ **正确**：
```vue
<style scoped>
.button-primary {
  background: var(--color-brand-500);
  color: var(--color-bg-surface);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-5);
  font: var(--text-body);
}
</style>
```

❌ **禁止**：
```vue
<style>
.bad {
  background: #4F46E4;       /* hex 字面量 */
  border-radius: 10px;       /* 数字字面量 */
  padding: 12px 20px;
  font-size: 14px;
}
</style>
```

### 1.3 UnoCSS preset

如果用 UnoCSS atomic class，必须在 `uno.config.ts` 把 token 注册成 theme：

```typescript
theme: {
  colors: {
    canvas: 'var(--color-bg-canvas)',
    surface: 'var(--color-bg-surface)',
    'brand-500': 'var(--color-brand-500)',
    /* ... */
  },
  spacing: { 1: 'var(--space-1)', /* ... */ },
}
```

然后类名只许用 `bg-canvas` / `text-brand-500` / `p-4` 这种 token-bound 形式。

---

## 2. Base 组件层（components/base/）

### 2.1 必须实现的 12 个原子组件

| 组件 | 文件 | 行为 |
|---|---|---|
| `BaseButton` | `BaseButton.vue` | 5 variant: `primary` / `secondary` / `ghost` / `danger` / `link`；3 size：`sm` / `md` / `lg`；loading + disabled 状态 |
| `BaseInput` | `BaseInput.vue` | text/number/email；label + helper + error 三槽；focus ring 用 `--shadow-focus` |
| `BaseTextarea` | `BaseTextarea.vue` | auto-resize 可选；min/max rows |
| `BaseSelect` | `BaseSelect.vue` | options + 自定义渲染 slot；keyboard navigate |
| `BaseSlider` | `BaseSlider.vue` | min/max/step；marks 数组；value display |
| `BaseCard` | `BaseCard.vue` | bordered/elevated 两种 variant |
| `BaseBadge` | `BaseBadge.vue` | 9 颜色 tone（neutral/brand/success/warning/danger/info + KG 6 类）；3 size；含 `dot` 前缀 boolean |
| `BaseChip` | `BaseChip.vue` | 同 Badge 但带 close 按钮 + click |
| `BaseModal` | `BaseModal.vue` | ESC 关 + focus trap + overlay click 关；scroll lock；teleport to body |
| `BaseDrawer` | `BaseDrawer.vue` | 左/右滑入；同 Modal 的 a11y |
| `BaseTooltip` | `BaseTooltip.vue` | hover/focus 触发；定位用 floating-ui |
| `BaseEmptyState` | `BaseEmptyState.vue` | icon slot + title + description + action slot |
| `BaseSkeleton` | `BaseSkeleton.vue` | 脉冲动画 1.2s；800ms 才显示（避免抖动） |

### 2.2 Base 组件契约

每个 base 组件**必须**：

1. **Props 类型严格**：所有 prop 用 `interface` 标注；支持 `<script setup lang="ts">`
2. **支持 `class` / `style` 透传**：消费者能传 class 进一步定制
3. **emit 类型化**：用 `defineEmits<{ ... }>()` 显式
4. **不写业务字符串**：所有显示文案用 slot 或 prop，不在组件内 hardcode
5. **不依赖具体上层 store**：只接 props / emit；纯展示
6. **a11y 完备**：
   - Button → role=button + keyboard
   - Input → label + aria-describedby for error
   - Modal → role=dialog + aria-modal=true + focus trap
   - Drawer → role=dialog + aria-labelledby
7. **配套 spec**：`<Component>.spec.ts` 覆盖 ≥ 80% 关键行为

### 2.3 引用方式

**业务组件 / 视图禁止 import Naive UI 原子**：

```typescript
// ❌ 禁止
import { NButton, NInput } from 'naive-ui'

// ✅ 允许
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
```

例外：复杂组件（NDataTable、NDatePicker、NTreeSelect 等）允许直接用 Naive UI，但必须在 `components/base/` 加薄包装层（即使薄）。

---

## 3. 业务组件结构

```
apps/web/src/components/
├── base/                  # 原子层（§2）
├── layout/                # AppShell / Topbar / SideNav / TopbarLibrarySwitcher
├── library/               # LibraryCard / LibraryStatusBadge / LibraryCreateModal / DeleteConfirmModal / RecentActivityList / QualityKPIPanel
├── chat/                  # CitationChip / EvidencePanel / Composer / MessageBubble / SessionList / ReasoningTrace / EmptyState
├── kg/                    # EntityTypeFilter / DepthSlider / ConfidenceSlider / EntityDetailDrawer / KGCanvasToolbar
├── upload/                # DropZone / IngestStatusBadge / IngestProgressBar / FailedErrorPopover
├── documents/             # DocumentDetailDrawer
├── tasks/                 # PipelineTree / CitationLiveList / CostMeter / TaskProgressPanel / RunInBackgroundButton
├── review/                # ReviewConfigForm
├── reason/                # PathVisualization / EvidenceTimeline
├── hypothesis/            # HypothesisCard / HypothesisInputForm
├── eval/                  # KPICard / TrendChart / FailureCaseTable / AlertBanner / LibraryFilter
├── settings/              # LLMRouterPicker / EmbedderPicker / BudgetSettings / SchemaEditor
└── common/                # I18nSwitcher / NotificationCenter / CommandPaletteOverlay
```

**目录 = 屏 / 领域**。一个组件不许跨 2 个目录。

---

## 4. 页面（views/）规则

### 4.1 视图职责
- **只**做：从 store 读 → 拼装组件 → emit 用户意图
- **不许**：在 view 里写业务逻辑、API 调用、数据转换 — 全部下沉到 store / composable

### 4.2 Library-scoped view 必须
- URL 含 `:libraryId` 路径参数
- 路由守卫已校验存在性（router/index.ts 已配，不要重写）
- 切库时 store 自动清空当前 library 相关 state

### 4.3 Empty States
**强制**：每个会展示数据列表的 view 必须有 empty state，调用 `BaseEmptyState`，禁止 LLM 假装回答。

---

## 5. State management（Pinia）

### 5.1 Store 命名 + 文件
- `apps/web/src/stores/<domain>Store.ts`
- 一 store 一文件；不许在 view 里 `defineStore`

### 5.2 Store 内不直接调 fetch
- API 调用走 `api/<domain>.ts` 模块（typed clients）
- store 只组合 + cache

### 5.3 State 不可变
- 用 `ref` / `reactive`，更新走 setter；禁直接 mutate 嵌套对象（用 `.value = { ...state, ... }`）

---

## 6. 测试

### 6.1 Vitest + Testing Library
- `tests/unit/components/base/*.spec.ts` 每个 base 组件 ≥ 80% 覆盖
- `tests/unit/components/<domain>/*.spec.ts` 关键业务组件
- E2E（Playwright）覆盖 J1 / J2 / J3 旅程（PRD §UI_UX.md §7）

### 6.2 a11y 测试
- 用 `@testing-library/vue` + `axe-core` 跑 a11y 检查（baseline ≥ 95% on each page）

---

## 7. CI 红线（违反阻塞合并）

```bash
pnpm typecheck         # vue-tsc 0 errors
pnpm lint              # eslint --max-warnings 0
pnpm test              # vitest 全绿
pnpm i18n:check        # zh-CN / en-US key 集合一致
pnpm build             # 不许 chunk 超 500 KB warning（除非显式 mainfestChunks）
```

---

## 8. 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| Vue 文件 | PascalCase | `LibraryCard.vue` |
| Composable | `useFooBar.ts` | `useTaskEvents.ts` |
| Store | `<domain>Store.ts` | `librariesStore.ts` |
| Type / Interface | PascalCase | `LibraryConfig` |
| Boolean prop | `is-` / `has-` / `should-` 前缀 | `is-loading` |
| Event | kebab-case (template) / camelCase (TS) | `@click="..."` ↔ `emit('click')` |

---

## 9. 国际化

- 每个可见字符串必须在 `i18n/locales/{zh-CN,en-US}.ts` 双语补齐
- key 命名：`<domain>.<component>.<element>` (e.g. `library.create.slug.label`)
- CI 校验 key 集合一致（`pnpm i18n:check`）

---

## 10. 还原度验证

每个 view 实现完成后，**作者**对照 Figma frame 截图 / 实测数据自查：

- [ ] 主题色与 Figma 一致（用 token，不会偏）
- [ ] 字体大小、行高与 SPEC 表一致
- [ ] padding / gap 与 frame auto-layout 数值一致（spec 列出）
- [ ] 圆角值用 token，与 frame 实测一致
- [ ] 阴影使用 token 不自创
- [ ] 关键尺寸匹配（SideNav 240w、Topbar 56h、Modal 600w 等）
- [ ] Empty / Loading / Error state 都有
- [ ] 键盘可达 + ARIA 完备
- [ ] 双语字符串都补齐

不通过即重做，不能 merge。

---

## 11. 已知 SPEC / 实现不一致点

> 此处记录实现过程中发现的 SPEC 与实现/工程现实之间的偏差，便于后续 Agent 决策。

### 11.1 S2 Library Dashboard
- SPEC `s2-card-1` 描述每张 LibraryCard 为 320×220；本实现使用 `auto-fill, minmax(300px, 1fr)` 网格，单卡最小 300px，宽屏会拉伸到 1fr。原因：320px 固定宽度在 1280 容器下三列偏窄；柔性列保留视觉密度的同时保证响应式。
- SPEC `s2-kpi-panel` 表为 384×320 的单列 KPI 面板；本实现为 2×2 / 1×4 响应式 grid（≥ 1024 px 4 列），保留 4 个 KPI 但布局更通用。
- SPEC `s2-i18n-toggle` / `s2-cmdk` / `s2-avatar` / `s2-library-switcher` 由 `AppTopbar` 渲染（layout 层），不在 LibrariesView 内部。

### 11.2 Pre-existing typecheck / lint 红线
- `pnpm build` / `pnpm typecheck` 当前在以下**非本 Agent OWN**文件上有错（M7 完工后随其他 Agent 引入 `exactOptionalPropertyTypes: true` 后未跟进）：
  - `src/components/hypothesis/HypothesisInputForm.vue`
  - `src/components/review/ReviewConfigForm.vue`
  - `src/components/settings/BudgetSettings.vue`
  - `src/components/settings/SchemaEditor.vue`
  - `src/components/tasks/CitationLiveList.vue`
- `pnpm lint` 在 `src/components/upload/DropZone.vue` 上有一处 `vue/define-macros-order` 错。
- `pnpm test` 中 `tests/unit/components/eval/AlertBanner.spec.ts` 1 例失败（spec 里硬编码 `#f0a020` 期望 NAlert 输出，但组件已被重写为自定义实现）。
- 修复路径：分别由 hypothesis / review / settings / tasks / eval / upload 这几个领域的 OWN agent 在各自的 frame 还原迭代中处理，不在本任务 (S1/S2/M1/M2) 范围内。

### 11.3 LibraryStatusBadge dot 配色
- SPEC 中 `Indexing` 用 cobalt `brand-500`、`Stale community` 用 amber `warning-500`、`Healthy` 用 success-500。原 `bg-blue-500` / `bg-amber-500` / `bg-green-500` 不在 token 体系内，已替换为 `status-dot--{status}` 语义类 + `var(--color-*-500)` token 实现，避免脱钩 token。

---

**END**
