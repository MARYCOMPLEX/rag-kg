# 01 · Tokens + 输入原子组件交互规范

> 范围：Design Tokens（Cobalt Lab）+ BaseButton / BaseInput / BaseTextarea / BaseSelect / BaseSlider / Checkbox + Radio + Toggle
> 适用：RAG-KG Copilot 前端（Vue 3.4 + Pinia + Naive UI + UnoCSS）
> 原则：业务层只用 `components/base/*` 薄包装；禁止 hex 字面量；禁止越过 token 直接写颜色 / 间距。

---

## §01 Tokens — Cobalt Lab 设计系统总览

### 视觉观察
图中将 Token 体系拆为五大列：
1. **Neutrals (Warm Gray)** — 6 阶暖灰，从 `bg-canvas` 一路下沉到 `text-primary`，**没有纯白也没有纯黑**，这是 Cobalt Lab 区别于 Material 的关键决定。
2. **Brand Cobalt** — 5 阶钴蓝紫，brand-500 为主交互色，brand-600 hover，brand-100/200 用于浅底（Selected Row、checked Toggle 内嵌阴影）。
3. **Semantic** — success / warning / danger / info-cyan 四个语义色 + **CitationChip 专用 info-cyan**（视觉传递"这是引用，不要点我当按钮"）。
4. **KG Entity Types** — 6 个高饱和点状色，仅用于知识图谱节点 / Library 圆点，不可外泄到通用 UI。
5. **Typography / Spacing / Radius / Shadow** — Aa 36/28/22/20 字阶；4 px 网格 (4/8/12/16/20/24/32/40/48/64)；radius 6/10/14/20/999；shadow sm/md/lg + focus-ring。

### Token → UnoCSS theme key 映射表

| Category | Token Key | 值 | 用途 |
|---|---|---|---|
| **Color · Neutral** | `bg-canvas` | `#FAFAF9` | 页面底 |
| | `bg-surface` | `#FFFFFF` | 卡片 / Modal |
| | `bg-subtle` | `#F4F4F2` | 二级面板 / hover row |
| | `border-default` | `#E5E5E2` | 1 px 边 |
| | `text-tertiary` | `#9A9A95` | placeholder / helper |
| | `text-secondary` | `#6B6B66` | 次级文字 / label |
| | `text-primary` | `#1A1A1A` | 主体 |
| **Color · Brand** | `brand-100` | `#EEEBFE` | 浅底 selected |
| | `brand-200` | `#D8D2FB` | toggle track checked 浅化 |
| | `brand-400` | `#6A60E8` | focus ring 内核 |
| | `brand-500` | `#4F46E4` | 主按钮 / 主滑块 |
| | `brand-600` | `#3B30D9` | hover / active |
| **Color · Semantic** | `success` | `#10B881` | 成功提示 |
| | `warning` | `#F59E0A` | 警告 |
| | `danger`  | `#EE4444` | 错误 / Danger 按钮 |
| | `info`    | `#06B6D3` | **CitationChip 专属**，业务别复用 |
| **Color · KG Entity** | `kg-concept` `kg-method` `kg-dataset` `kg-metric` `kg-author` `kg-venue` | 6 色 | 仅图谱节点 / Library 圆点 |
| **Spacing** | `1` … `16` | 4 px 步进 (4/8/12/16/20/24/32/40/48/64) | 必须 4 px 对齐 |
| **Radius** | `chip` / `btn` / `card` / `modal` / `pill` | 6 / 10 / 14 / 20 / 9999 | 不准自由值 |
| **Font Size** | `xs` 12 / `sm` 13 / `base` 14 / `md` 16 / `lg` 20 / `xl` 22 / `2xl` 28 / `display` 36 | — | UI 默认 14，正文 16 |
| **Font Family** | `sans` Inter / `mono` JetBrains Mono | — | chunk_id / DOI / 数值必须 mono |
| **Shadow** | `sm` 单层 1/2 / `md` 双层 4/8 / `lg` 三层 12/24 / `focus` `0 0 0 3px rgb(79 70 229 / .20)` | — | focus 单独 token，避免业务自拼 |
| **Z-index** | `dropdown` 1000 / `sticky` 1020 / `modal` 1050 / `popover` 1070 / `tooltip` 1080 / `toast` 1090 | — | 6 段，禁止 9999 |
| **Motion** | `dur-hover` 120 ms / `dur-modal` 200 ms / `dur-caret` 22 ms / `ease-out` `cubic-bezier(.2,.8,.2,1)` / `spring` `cubic-bezier(.34,1.56,.64,1)` | — | 流式 token caret 固定 22 ms |

### `uno.config.ts` 片段

```ts
// uno.config.ts
import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss'

export default defineConfig({
  presets: [presetUno(), presetAttributify(), presetIcons()],
  theme: {
    colors: {
      bg: { canvas: '#FAFAF9', surface: '#FFFFFF', subtle: '#F4F4F2' },
      border: { default: '#E5E5E2', strong: '#D4D4D0' },
      text: { primary: '#1A1A1A', secondary: '#6B6B66', tertiary: '#9A9A95', inverse: '#FAFAF9' },
      brand: {
        100: '#EEEBFE', 200: '#D8D2FB', 300: '#B5ABF4',
        400: '#6A60E8', 500: '#4F46E4', 600: '#3B30D9', 700: '#2C23A8',
      },
      success: '#10B881', warning: '#F59E0A', danger: '#EE4444', info: '#06B6D3',
      kg: {
        concept: '#4F46E4', method: '#F59E0A', dataset: '#10B881',
        metric: '#06B6D3', author: '#EE4444', venue: '#7C3AED',
      },
    },
    spacing: {
      1: '4px', 2: '8px', 3: '12px', 4: '16px', 5: '20px',
      6: '24px', 8: '32px', 10: '40px', 12: '48px', 16: '64px',
    },
    borderRadius: { chip: '6px', btn: '10px', card: '14px', modal: '20px', pill: '9999px' },
    fontFamily: {
      sans: 'Inter, "PingFang SC", system-ui, sans-serif',
      mono: '"JetBrains Mono", "SF Mono", Menlo, monospace',
    },
    fontSize: {
      xs: ['12px', '16px'], sm: ['13px', '18px'], base: ['14px', '20px'],
      md: ['16px', '24px'], lg: ['20px', '28px'], xl: ['22px', '30px'],
      '2xl': ['28px', '36px'], display: ['36px', '44px'],
    },
    boxShadow: {
      sm: '0 1px 2px rgb(0 0 0 / .04), 0 1px 1px rgb(0 0 0 / .03)',
      md: '0 4px 8px rgb(0 0 0 / .06), 0 2px 4px rgb(0 0 0 / .04)',
      lg: '0 12px 24px rgb(0 0 0 / .08), 0 4px 8px rgb(0 0 0 / .04)',
      focus: '0 0 0 3px rgb(79 70 229 / .20)',
    },
    zIndex: {
      dropdown: '1000', sticky: '1020', modal: '1050',
      popover: '1070', tooltip: '1080', toast: '1090',
    },
    transitionDuration: { hover: '120ms', modal: '200ms', caret: '22ms' },
    transitionTimingFunction: {
      out: 'cubic-bezier(.2,.8,.2,1)',
      spring: 'cubic-bezier(.34,1.56,.64,1)',
    },
  },
  shortcuts: {
    'focus-ring': 'outline-none ring-3 ring-brand-500/20',
    'card': 'bg-bg-surface rounded-card shadow-sm border border-border-default',
    'mono-num': 'font-mono tabular-nums',
  },
})
```

### 强制规则：禁止 hex 字面量

**ESLint**（`.eslintrc.cjs`）：
```js
'no-restricted-syntax': ['error', {
  selector: 'Literal[value=/^#[0-9a-fA-F]{3,8}$/]',
  message: '禁止 hex 字面量；请使用 UnoCSS theme token（如 brand-500 / text-primary）',
}],
```

**Stylelint**（`stylelint.config.cjs`）：
```js
rules: {
  'color-no-hex': true,
  'declaration-property-value-disallowed-list': {
    '/^(color|background|border|fill|stroke)/': ['/^#/', '/^rgb/', '/^hsl/'],
  },
  'unit-disallowed-list': ['px', { ignoreProperties: { px: ['/^border/', '/^outline/'] } }],
}
```
> `px` 在 border / outline 之外禁用，强制走 spacing token；`color-no-hex` 拦截 CSS / SCSS 中的 hex；ESLint 拦截 TS / Vue 模板中的 hex。

### UI 参数（来自 UI_PROMPTS §01 全 token 表）

#### Color · Neutral
| Token | Hex | 用途 |
|---|---|---|
| bg-canvas | #FAFAF9 | 页面底（暖白） |
| bg-surface | #FFFFFF | 卡片 / Modal 底 |
| bg-subtle | #F4F4F2 | hover / 二级填充 |
| bg-muted | #EAEAE5 | 分隔条填充 / Slider rail |
| border-subtle | #E4E4E0 | 卡片描边 |
| border-default | #E5E5E2 | 输入描边 |
| border-strong | #8C8C82 | focus 前的强描边 |
| text-primary | #1A1A1A | 主体文字 |
| text-secondary | #515151 | 次级文字 |
| text-tertiary | #9A9A95 | placeholder / helper |
| text-disabled | #BDBDB8 | 禁用文字 |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：`bg-subtle #F4F4F1 → #F4F4F2`、`border-default #D3D3CE → #E5E5E2`、`text-tertiary #8C8C82 → #9A9A95`。

#### Color · Brand
| Token | Hex | 用途 |
|---|---|---|
| brand-50 | #EDF0FF | hover 浅底 |
| brand-100 | #DCE2FF / #EEEBFE | selected 行底（SPEC = #EEEBFE） |
| brand-200 | #B2BCF4 / #D8D2FB | toggle track 浅化（SPEC = #D8D2FB） |
| brand-300 | #8D9FFF | — |
| brand-400 | #6A60E8 | focus ring 内核（仅 SPEC） |
| brand-500 | #4F46E4 | PRIMARY 主交互色 |
| brand-600 | #3B30D9 | hover |
| brand-700 | #2A1FAF / #2C23A8 | active / 深底文字 |

#### Color · Semantic
| Token | 50 | 500 | 700 |
|---|---|---|---|
| success | #EBFCF5 | #10B881 | #047856 |
| warning | #FFFAEB | #F59E0A | #B45208 |
| danger | #FDF1F1 | #EE4444 | #B91B1B |
| info / citation | #EBFDFF | #06B6D3 | #0E7490 |

#### Color · KG Entity
| Token | Hex |
|---|---|
| kg-concept | #4F46E4 |
| kg-method | #10B881 |
| kg-dataset | #F59E0A |
| kg-metric | #06B6D3 |
| kg-author | #A854F7 |
| kg-venue | #EB4799 |

#### Typography（Inter / JetBrains Mono）
| Scale | size / line-height | weight | 用途 |
|---|---|---|---|
| display | 36 / 43.6 | 700 | Onboarding hero |
| h1 | 28 / 33.9 | 700 | 页标题 |
| h2 | 22 / 26.6 | 700 | 区块标题 |
| h3 | 20 / 24.2 | 600 | 卡片标题 |
| h4 | 18 / 21.8 | 600 | 子标题 |
| body-lg | 16 / 22 | 400 | 长文阅读 |
| body | 14 / 16.9 | 400 | UI 默认 |
| body-sm | 13 / 15.7 | 400 | helper / 次级 UI |
| caption | 12 / 14.5 | 400 | 注释 / counter |
| meta | 11 / 13.3 | 500 | UPPERCASE label |
| mono | 13 / 20 | 400 | chunk_id / DOI / 分值 |

数字一律 `tabular-nums`；CJK 走 PingFang SC fallback。

#### Spacing（4 px 步进）
| Token | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|
| 值 | 4 | 8 | 12 | 16 | 20 | 24 | 32 | 40 | 48 | 64 |

Grid：12 列 / 24 gutter / max 1280 / 侧 safe 32。

#### Radius
| Token | chip | btn / input | card | modal / big-panel | pill |
|---|---|---|---|---|---|
| 值 | 6 | 10 | 14 | 20 | 9999 |

#### Shadow
| Token | 值 | 用途 |
|---|---|---|
| sm | `0 1px 2px rgba(15,15,20,.04)` | 卡片平铺 |
| md | `0 4px 12px rgba(15,15,20,.06)` | 抬升卡片 / popover |
| lg | `0 12px 32px rgba(15,15,20,.10)` | modal |
| focus | `0 0 0 3px rgba(79,70,229,.20)` | a11y 焦点环 |

#### Motion
| Token | duration | easing | 用在 |
|---|---|---|---|
| dur-hover | 120 | ease-out | hover / focus / border / bg |
| dur-modal | 200 | cubic-bezier(.2,.8,.2,1) | modal 入场 / dropdown |
| dur-page | 240 | ease | 路由切换 |
| dur-caret | 22 | linear | 流式 token caret |
| caret-blink | 1.0 Hz | — | caret 闪烁 |
| spring | 320 | cubic-bezier(.34,1.56,.64,1) | KG 节点 settle / 离散吸附 |

#### Z-index
| dropdown | sticky | modal | popover | tooltip | toast |
|---|---|---|---|---|---|
| 1000 | 1020 | 1050 | 1070 | 1080 | 1090 |

#### Icon
| 库 | 描边 | 尺寸 |
|---|---|---|
| Lucide line | 1.5 | 16 / 20 / 24 |

#### 完整 `uno.config.ts` 片段（≤ 50 行示意）
```ts
import { defineConfig, presetUno } from 'unocss'
export default defineConfig({
  presets: [presetUno()],
  theme: {
    colors: {
      bg: { canvas: '#FAFAF9', surface: '#FFFFFF', subtle: '#F4F4F2', muted: '#EAEAE5' },
      border: { subtle: '#E4E4E0', default: '#E5E5E2', strong: '#8C8C82' },
      text: { primary: '#1A1A1A', secondary: '#515151', tertiary: '#9A9A95', disabled: '#BDBDB8' },
      brand: { 50: '#EDF0FF', 100: '#EEEBFE', 200: '#D8D2FB', 300: '#8D9FFF',
               400: '#6A60E8', 500: '#4F46E4', 600: '#3B30D9', 700: '#2C23A8' },
      success: { 50: '#EBFCF5', 500: '#10B881', 700: '#047856' },
      warning: { 50: '#FFFAEB', 500: '#F59E0A', 700: '#B45208' },
      danger:  { 50: '#FDF1F1', 500: '#EE4444', 700: '#B91B1B' },
      info:    { 50: '#EBFDFF', 500: '#06B6D3', 700: '#0E7490' },
      kg: { concept: '#4F46E4', method: '#10B881', dataset: '#F59E0A',
            metric:  '#06B6D3', author: '#A854F7', venue:   '#EB4799' },
    },
    spacing: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 5: '20px',
               6: '24px', 8: '32px', 10: '40px', 12: '48px', 16: '64px' },
    borderRadius: { chip: '6px', btn: '10px', card: '14px', modal: '20px', pill: '9999px' },
    fontFamily: { sans: 'Inter, "PingFang SC", system-ui, sans-serif',
                  mono: '"JetBrains Mono", "SF Mono", Menlo, monospace' },
    fontSize: { meta: ['11px','13.3px'], xs: ['12px','14.5px'], sm: ['13px','15.7px'],
                base: ['14px','16.9px'], md: ['16px','22px'], lg: ['20px','24.2px'],
                xl: ['22px','26.6px'], '2xl': ['28px','33.9px'], display: ['36px','43.6px'],
                mono: ['13px','20px'] },
    boxShadow: { sm: '0 1px 2px rgba(15,15,20,.04)',
                 md: '0 4px 12px rgba(15,15,20,.06)',
                 lg: '0 12px 32px rgba(15,15,20,.10)',
                 focus: '0 0 0 3px rgba(79,70,229,.20)' },
    zIndex: { dropdown:'1000', sticky:'1020', modal:'1050',
              popover:'1070', tooltip:'1080', toast:'1090' },
    transitionDuration: { hover:'120ms', modal:'200ms', page:'240ms', caret:'22ms', spring:'320ms' },
    transitionTimingFunction: { out: 'cubic-bezier(.2,.8,.2,1)',
                                spring: 'cubic-bezier(.34,1.56,.64,1)' },
  },
  shortcuts: {
    'focus-ring': 'outline-none shadow-focus',
    'mono-num': 'font-mono tabular-nums',
  },
})
```

---

## §02-A BaseButton — 主操作 / 次操作 / 工具链接

### 视觉
图中给出 **5 个变体 × 4 个尺寸 × 5 个状态** 的全矩阵：Primary（实心钴蓝紫）/ Secondary（白底灰描边）/ Ghost（无底，hover 起浅灰底）/ Danger（实心红）/ Link（纯文字 + 下划线）。圆角 10 px（btn token），高度梯度 28 / 32 / 36 / 44。

### 状态
- **default** — 静止态，符合 variant 主色
- **hover** — 颜色加深（brand-600）/ 灰阶加深，120 ms 过渡
- **active / pressed** — 再深一档 + 内嵌 1 px 阴影（视觉下沉）
- **disabled** — **用 token `bg-subtle` + `text-tertiary` 灰色实体**，**禁止 opacity 半透明**（图中明确："Don't use opacity"）
- **loading** — 文字左侧出现 spinner，按钮宽度锁定（避免抖动），文本保留以维持 hit target
- **special** — Continue 带右箭头 / 删除带 trash icon / 流式 token "Generating…" 带流光

### 交互
- 鼠标：hover 触发 120 ms color transition；click 触发 spring 1px scale-down (0.98)
- 键盘：Tab 进入 → Enter / Space 触发；Esc 不应该触发（除非作为 Modal close）
- 触屏：min hit target 44×44；active 态延迟 100 ms 防误触

### A11y
- `role="button"`（如果用 `<button>` 标签自动具备）
- `aria-busy="true"` when loading
- `aria-disabled="true"` 而非仅 `disabled`（因为 disabled 在 a11y 树中不可聚焦不可读屏）
- Focus ring：`shadow-focus` (3 px brand-500/20)，**绝不允许 outline:none 不补焦点**

### 动效
- color/bg：`120ms ease-out`
- scale-down on press：`spring (.34,1.56,.64,1)`
- loading spinner：旋转 800 ms linear

### Vue 实现

```ts
// components/base/BaseButton.vue
<script setup lang="ts">
import { NButton } from 'naive-ui'
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'link'
type Size = 'xs' | 'sm' | 'md' | 'lg'
const props = defineProps<{
  variant?: Variant; size?: Size;
  loading?: boolean; disabled?: boolean;
  icon?: string; iconPosition?: 'left' | 'right';
}>()
const emit = defineEmits<{ (e: 'click', ev: MouseEvent): void }>()
</script>
```
- **底层**：Naive UI `NButton`（保 a11y / loading 内建）
- **包装策略**：把 Naive 的 `type` 字段映射成业务语义 `variant`；通过 `:theme-overrides` 注入 token（不写死 hex）
- **辅助 lib**：
  - `@vueuse/core` 的 `useElementHover` + `useElementSize`（loading 锁宽）
  - `@formkit/auto-animate` — 文本 ↔ spinner 切换零抖动
- **联动**：`emit('click')` → 调用方注入 Pinia action（如 `useChatStore().send()`），按钮自己不耦合 store

### 与全局的耦合点
- Continue / Resume 在 ChatComposer 由 `useChatStore.isStreaming` 控制 disabled
- Danger 变体上要包一层 `useConfirm()`（floating-vue popover），二次确认才 emit click

#### UI 参数（来自 UI_PROMPTS §02-A）

尺寸（高度 / 内边距 上下/左右 / 字体）：
| size | height | padding | font |
|---|---|---|---|
| sm | 32 | 8 / 12 | body-sm 13/15.7 |
| md | 40 | 10 / 16 | body 14/16.9 |
| lg | 48 | 12 / 20 | body-lg 16/22 |

所有变体圆角统一 `btn = 10`；图标用 Lucide 16 / stroke 1.5。

变体 × 状态：
| variant / 状态 | default 背景 | default 文字 | default 边框 | hover | active | disabled |
|---|---|---|---|---|---|---|
| Primary | brand-500 #4F46E4 | #FFFFFF | — | brand-600 #3B30D9 | brand-700 #2A1FAF + 内嵌阴影 | bg-subtle #F4F4F2 / text-disabled #BDBDB8 |
| Secondary | bg-surface #FFFFFF | text-primary #1A1A1A | 1 border-default #E5E5E2 | bg-subtle #F4F4F2 | 再深一档 + 内阴影 | bg-subtle / text-disabled |
| Ghost | transparent | text-primary #1A1A1A | — | bg-subtle #F4F4F2 | bg-muted #EAEAE5 | text-disabled #BDBDB8 |
| Danger | danger-500 #EE4444 | #FFFFFF | — | #D33A3A | danger-700 #B91B1B | bg-subtle / text-disabled |
| Link | transparent | brand-600 #3B30D9 | — | underline | brand-700 #2A1FAF | text-disabled |

| 类别 | 值 |
|---|---|
| 圆角 | 10 |
| 焦点环 | `0 0 0 3px rgba(79,70,229,.20)` |
| 动效（color/bg） | 120 ms ease-out |
| 动效（press scale） | spring `cubic-bezier(.34,1.56,.64,1)` → 0.98 |
| Loading spinner | 800 ms linear（替换 icon 位） |
| Hit target | min 44×44（触屏） |
| Disabled 禁用方式 | bg-subtle + text-disabled，禁止 `opacity` |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：Secondary 边框 `border-default #D3D3CE → #E5E5E2`；hover/disabled 底 `#F4F4F1 → #F4F4F2`。

---

## §02-B BaseInput — 单行输入 / Slug / 命令搜索

### 视觉
图中 6 行示例覆盖：**Empty / Filled / Focused / Error / Disabled / WithIcon+Shortcut**。
- 高度 40，圆角 10（btn token），1 px 边
- Focus 态：边变 brand-500 + **3 px focus ring**（brand-500/20）
- Error 态：边变 danger + **下方 helper 文字变 danger**，**不要红底**
- WithIcon：左 16×16 icon（搜索）+ 右 chip `⌘K`（mono 字体，bg-subtle 底）

### 状态
default / hover（边 darken 到 border-strong）/ focus / filled / error / disabled / readonly

### 交互
- Tab 进入 → Esc 失焦 → Enter 触发 submit（由父表单决定）
- `⌘K` / `Ctrl+K` 全局聚焦（command palette）
- 长按 / 双击全选；右键菜单走浏览器默认
- 粘贴时若超出 maxlength 截断 + 提示

### A11y
- `<label for=…>` 必须，**不许用 placeholder 替代 label**（图中所有示例都有上方 LIBRARY ID · SLUG 标签）
- `aria-invalid="true"` + `aria-describedby="helperId"` for error
- Placeholder 用 `text-tertiary`（4.5:1 对正文 contrast 不够 → 不能承担信息）

### 动效
- border / ring：`120ms ease-out`
- error shake 可选：horizontal 4 px × 3 次 / 200 ms（vee-validate fail 时）

### Vue 实现
- **底层**：`NInput`
- **辅助 lib**：
  - `vee-validate + zod` — 表单层校验（slug `/^[a-z0-9-]{3,30}$/`），把 zod error 桥到 `helperText` slot
  - `@vueuse/core` 的 `useMagicKeys` — 注册 ⌘K 全局快捷键
  - `@vueuse/core` 的 `useFocus` — 暴露 `focus()` / `blur()` 给父组件
- **v-model**：`v-model:value` 默认 + `v-model:debounced`（命令搜索场景，350 ms）

### 联动
- 搜索框 → `useCommandPaletteStore`
- Slug → `useLibraryStore.createDraft.slug`，blur 时校验唯一性（异步 zod refine）

#### UI 参数（来自 UI_PROMPTS §02-B）

| 类别 | default | focus | error | disabled |
|---|---|---|---|---|
| 宽度 | 360（slug/name M1 = 536） | — | — | — |
| 高度 | 44（PROMPTS）/ 40（既有规范） | — | — | — |
| 内边距 | 12 / 14 | — | — | — |
| 圆角 | 10 | — | — | — |
| 字体 | Inter Regular body 14/16.9 | — | — | — |
| 背景 | bg-surface #FFFFFF | bg-surface | bg-surface | bg-subtle #F4F4F2 |
| 边框 | 1 border-default #E5E5E2 | 1 brand-500 #4F46E4 | 1 danger-500 #EE4444 | 1 border-default |
| 文字 | text-primary #1A1A1A | text-primary | text-primary | text-disabled #BDBDB8 |
| Placeholder | text-tertiary #9A9A95 | — | — | — |
| 焦点环 | — | `0 0 0 3px rgba(79,70,229,.20)` | — | — |
| Helper 文字 | caption 12/14.5 text-tertiary | — | body-sm 13/15.7 danger-700 #B91B1B | — |
| Label | meta 11/13.3 500 UPPERCASE text-tertiary，margin-bottom 4 | — | — | — |
| Prefix icon | Lucide 16 stroke 1.5 text-tertiary | — | — | — |
| Suffix chip (⌘K) | 24×20，bg-subtle，mono | — | — | — |
| 动效 | border / ring 120 ms ease-out | — | error shake 4 px × 3 / 200 ms（可选） | — |
| Debounce（搜索） | 350 ms（v-model:debounced） | — | — | — |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：边框 `border-default #D3D3CE → #E5E5E2`；placeholder/helper 色 `text-tertiary #8C8C82 → #9A9A95`；disabled 底 `#F4F4F1 → #F4F4F2`。高度 PROMPTS 写 44、既有规范沿用 40，**前端实现以既有规范 40 为准**（与 Slug/M1 内的 44 是不同档位）。

---

## §02-C BaseTextarea — 多行 / Auto-resize

### 视觉
图中 4 个态（Empty / Filled / Focused / Error）+ 底部 4 张 auto-resize 时序图。
- 默认 360×120，最小 120 px，最大 240 px（4 张图示意「one line → two lines → three lines → max → scroll」）
- 圆角 14（注意是 card token 不是 btn）—— 比 input 更柔，因为它是"内容容器"
- focused 态 ring 内带文字"Focus ring (brand-500) for accessibility and keyboard navigation"
- error 态 helper：`Error state communicates issues with input field and validation messages.`

### 状态
empty / filled / focused / error / disabled / readonly / **at-max-height(scroll)**

### 交互
- Auto-resize：内容增加时 height 跟随，超过 max 出现垂直滚动条
- Cmd/Ctrl + Enter 提交（chat 场景），Enter 默认换行
- Shift + Enter 永远是换行（不可被覆盖）
- 拖拽右下角手柄禁用（auto-resize 与手动 resize 冲突）

### A11y
- `aria-multiline="true"`
- `aria-describedby` 指向 helper + 字数计数
- 字数计数右下角 `mono-num`，剩余 < 20 时变 warning，溢出变 danger

### 动效
- height transition `120ms ease-out`，**只在 grow 时启用**，shrink 立即（避免聊天框抖动）
- focus ring 同 input

### Vue 实现
- **底层**：`NInput type="textarea"`，关闭原生 resize
- **辅助 lib**：
  - `@vueuse/core` 的 `useTextareaAutosize` — 直接给 minHeight/maxHeight，省一层手写 ResizeObserver
  - `@formkit/auto-animate` 给 height transition
- **联动**：ChatComposer textarea → `useChatStore.draft`，Cmd+Enter → `useChatStore.send()`

#### UI 参数（来自 UI_PROMPTS §02-C）

| 类别 | default | focus | error | disabled |
|---|---|---|---|---|
| 尺寸 | 360 × 120（min-h 120 / max-h 240） | — | — | — |
| 内边距 | 12 / 14 | — | — | — |
| 圆角 | 14（card token，与 Input 的 10 区分） | — | — | — |
| 字体 | Inter Regular body 14/16.9 | — | — | — |
| 背景 | bg-surface #FFFFFF | bg-surface | bg-surface | bg-subtle #F4F4F2 |
| 边框 | 1 border-default #E5E5E2 | 1 brand-500 #4F46E4 | 1 danger-500 #EE4444 | 1 border-default |
| Placeholder | text-tertiary #9A9A95 | — | — | — |
| 焦点环 | — | `0 0 0 3px rgba(79,70,229,.20)` | — | — |
| Counter（右下） | caption 12/14.5 text-tertiary，剩余<20 warning，溢出 danger | — | — | — |
| 动效（grow） | height 120 ms ease-out（仅放大） | — | — | — |
| 动效（shrink） | 立即（避免抖动） | — | — | — |
| 提交快捷键 | Cmd/Ctrl + Enter | — | — | — |
| 换行 | Enter（默认）/ Shift+Enter 永远换行 | — | — | — |
| 原生 resize 手柄 | 关闭 | — | — | — |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：边框 `border-default` 色与 input 一致使用 `#E5E5E2`；disabled 底色统一为 `#F4F4F2`。

---

## §02-D BaseSelect — 下拉 / Library 切换

### 视觉
图中 trigger 是带左侧彩色 dot（KG entity color）+ 标签 + 右侧 chevron 的胶囊条；展开后下拉用 `shadow-md` + `radius-card`，每行 `dot + label + 右对齐 mono "2,184 docs"`，hover 行 `bg-subtle`；底部分隔线后是 `+ New Library` 的 brand-color action row。

### 状态
- **trigger**：default / hover / open / disabled
- **option row**：default / hover (`bg-subtle`) / selected (`bg-brand-100` + brand 左竖线 2 px) / disabled
- **list**：empty（"No libraries"）/ loading（3 行 skeleton）/ error（"Failed to load · Retry"）

### 交互
- Click trigger → open dropdown（200 ms modal duration，scale-y 0.96→1）
- 键盘：
  - Tab 进入 trigger，Enter / Space / Arrow Down 打开
  - 打开后 Arrow Up/Down 在 options 间循环，Home/End 跳首末
  - Enter 选中，Esc 关闭并把焦点还给 trigger
  - 类型搜索：连续键入字符走 prefix match（200 ms 内）
- 触屏：点外侧关闭；列表 > 6 项滚动，trigger 高度恒定

### A11y
- trigger：`role="combobox"` + `aria-expanded` + `aria-controls`
- listbox：`role="listbox"` + 每项 `role="option"` + `aria-selected`
- 不允许把 select 退化成 div + click 监听（必须真 listbox，否则读屏无法 announce）

### 动效
- 展开/收起：`200ms ease-out` scale-y + opacity
- 选项 hover：`120ms`
- 配 `floating-vue` 自动避开屏幕边缘，避免 dropdown 被裁

### Vue 实现
- **底层**：`NSelect` 或自封 `floating-vue` + `NScrollbar`
- **辅助 lib**：
  - `floating-vue` — middleware `flip` / `shift` / `size`，处理边界
  - `@vueuse/core` 的 `onClickOutside`、`useEventListener('keydown')`
  - `@tanstack/vue-virtual` — Library / Tag 列表 > 50 时虚拟化
- **联动**：trigger 选中 → `useLibraryStore.setCurrent(id)`，所有依赖 library 的 store action 自动重拉

#### UI 参数（来自 UI_PROMPTS §02-D）

Trigger：
| 类别 | default | hover | open | disabled |
|---|---|---|---|---|
| 尺寸 | 280 × 36 | — | — | — |
| 内边距 | 8 / 12 | — | — | — |
| 圆角 | 10 | — | — | — |
| 背景 | bg-surface #FFFFFF | bg-subtle #F4F4F2 | bg-surface | bg-subtle |
| 边框 | 1 border-default #E5E5E2 | 1 border-strong #8C8C82 | 1 brand-500 #4F46E4 | 1 border-default |
| 字体 | Inter body 14/16.9 text-primary | — | — | text-disabled |
| Leading dot | 12 × 12 圆 brand-500（或 kg-* 色） | — | — | — |
| Trailing caret | "▾" 12 px text-tertiary | — | — | — |

Popover panel：
| 类别 | 值 |
|---|---|
| 宽度 | 280（同 trigger） |
| 圆角 | 14（card token） |
| 背景 | bg-surface #FFFFFF |
| 阴影 | `0 12px 32px rgba(15,15,20,.10)`（shadow-lg） |
| 内边距 | 4（外壳）/ 选项行内 12 横向 |
| 选项行高 | 36 |

Option row：
| 状态 | 背景 | 文字 | 标识 |
|---|---|---|---|
| default | transparent | text-primary | dot 12×12 + slug + 右对齐 mono "2,184 docs" caption text-tertiary |
| hover | bg-subtle #F4F4F2 | text-primary | — |
| active / selected | brand-50 #EDF0FF（或 brand-100 #EEEBFE） | text-primary | 左侧 2 px brand-500 竖条 |
| disabled | transparent | text-disabled #BDBDB8 | — |

Sticky 底部 action row：「+ New Library」，前置 plus icon brand-600 #3B30D9，body-sm 600。

| 动效 | 值 |
|---|---|
| 展开 / 收起 | 200 ms ease-out scale-y 0.96→1 + opacity |
| 选项 hover | 120 ms ease-out |
| 边界处理 | floating-vue flip / shift / size |
| 虚拟化阈值 | 列表 > 50 项 |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：trigger 边框 `#D3D3CE → #E5E5E2`；hover 底 `#F4F4F1 → #F4F4F2`；caret 色 text-tertiary 取 `#9A9A95`。

---

## §02-E BaseSlider — k-hop / Confidence

### 视觉
图中 4 个示例：
1. **DEPTH · k-hop (1-hop / 2-hop / 3-hop)** — 离散三档，刻度文字标在 track 下方
2. 同上 2-hop 位置
3. 同上 3-hop（满档）
4. **CONFIDENCE = 0.65** — 连续 0.00–1.00，**右上角放一个 info-cyan 的数值徽章 `0.65`**（mono 字体）

Track 高 4 px，filled 用 brand-500，rail 用 bg-subtle；thumb 16×16 白底 brand 边 + 阴影 sm。

### 状态
default / hover (thumb scale 1.1) / dragging (thumb scale 1.15 + tooltip 浮起) / focus (focus ring on thumb) / disabled

### 交互
- 鼠标：拖动 thumb；点 track 跳到对应位置
- 键盘：Arrow Left/Right 单步；Shift+Arrow 10 ×步长；Home/End 跳首末；PageUp/PageDown 大步长
- 触屏：thumb 透明 hit area 扩到 32×32（视觉仍 16）
- 离散档位：吸附到 marks，松手 spring 回最近档（200 ms）

### A11y
- `role="slider"` + `aria-valuemin/max/now` + `aria-valuetext`（k-hop 场景必填 "2 hops"，否则读屏读 "2"无意义）
- 连续滑块上 mono 数值徽章必须 `aria-live="polite"`，拖动时不打断

### 动效
- 离散吸附：`spring`
- thumb hover/focus：`120ms`
- track fill：跟随 thumb，无独立动画

### Vue 实现
- **底层**：`NSlider`，覆盖 `marks` 用 KG-friendly 离散档
- **辅助 lib**：
  - `@vueuse/core` 的 `useDraggable` — 自定义 thumb 时备用
  - 数值徽章用 `BaseTag variant="info"`（chip token）
- **联动**：
  - k-hop → `useGraphStore.depth`，change 触发 cytoscape 重布局（debounce 200 ms）
  - confidence → `useRagStore.minScore`，change 触发结果重过滤

#### UI 参数（来自 UI_PROMPTS §02-E）

Track + Thumb：
| 类别 | default | hover | dragging | focus | disabled |
|---|---|---|---|---|---|
| Track 宽度 | 232 | — | — | — | — |
| Track 高度 | 4 | — | — | — | — |
| Track 圆角 | pill 9999 | — | — | — | — |
| Rail 背景 | bg-muted #EAEAE5 | — | — | — | bg-muted |
| Fill 背景 | brand-500 #4F46E4 | — | — | — | text-disabled #BDBDB8 |
| Thumb 尺寸 | 16 × 16 圆 | scale 1.1 | scale 1.15 | scale 1.1 | 16 × 16 |
| Thumb 背景 | #FFFFFF | — | — | — | bg-subtle |
| Thumb 边框 | 1.5 brand-500 | — | — | — | 1.5 border-default |
| Thumb 阴影 | shadow-sm `0 1px 2px rgba(15,15,20,.04)` | — | + tooltip 浮起 | focus ring `0 0 0 3px rgba(79,70,229,.20)` | — |
| Thumb hit area（触屏） | 32 × 32 透明扩展 | — | — | — | — |

Label / Marks / Badge：
| 类别 | 值 |
|---|---|
| 上方 Label | meta 11/13.3 500 UPPERCASE text-tertiary #9A9A95 |
| 下方 tick 文字 | caption 12/14.5 text-tertiary（如 "1-hop / 2-hop / 3-hop"） |
| Value badge（右上，连续滑块） | BaseTag info chip，圆角 6，mono 13/20，例 "0.65" |

| 类别 | 值 |
|---|---|
| 键盘步长 | 1 单位（Arrow）/ 10× 单位（Shift+Arrow）/ Home·End 跳首末 / PageUp·PageDown 大步 |
| 离散吸附动效 | spring `cubic-bezier(.34,1.56,.64,1)` 200 ms |
| Thumb hover/focus 动效 | 120 ms ease-out |
| Confidence 范围 | 0.00–1.00（默认 0.65，3 位小数显示 2 位） |
| Debounce（图谱重算） | 200 ms |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：label 色 `#8C8C82 → #9A9A95`。

---

## §02-F Checkbox / Radio / Toggle

### 视觉（图中 3×4 矩阵）
| 控件 | 尺寸 | default | hover | checked | disabled |
|---|---|---|---|---|---|
| Checkbox | 16×16 | 白底灰边方框 | 边 brand-400 | brand-500 实心 + 白勾 | bg-subtle + text-tertiary |
| Radio | 16×16 | 白底灰边圆 | 边 brand-400 | brand-500 实心 + 白心点 | 灰圆 |
| Toggle | 32×18 | 灰胶囊 + 白圆 | 灰深一档 | brand-500 胶囊 + 白圆右移 | bg-subtle |

### 状态 + 交互
- 三者都支持 **indeterminate**（checkbox 横线 / toggle 半 offset 不允许，radio 不存在 indeterminate）
- Space 切换 checked；Tab 进入；箭头键在 **同一 radiogroup** 内切换（roving tabindex）
- Toggle 的 click 区域必须包含 label（不只是胶囊本体）

### A11y
- `role="checkbox" / "radio" / "switch"`（toggle 必须 switch，不是 checkbox）
- `aria-checked` true/false/mixed
- Radio 用 `<fieldset><legend>` 包，否则读屏听不到"这是一组单选"
- Toggle 旁边的 Label 必须 `<label for="…">`，不要把文字写在 toggle 之外当兄弟

### 动效
- Checkbox 勾画：`stroke-dasharray` 反推 + `120ms ease-out`（视觉"刷"出来）
- Radio 内心点：`spring scale 0→1`
- Toggle 圆球：`200ms ease-out` translate；底色同步 fade

### Vue 实现
- **底层**：`NCheckbox` / `NRadio` / `NSwitch`
- **辅助 lib**：
  - `vee-validate` — checkbox group 表单值收集（如 KG entity type 过滤器）
  - 不需要 auto-animate（动画走 CSS / Naive 内建）
- **联动**：
  - Checkbox group → `useFilterStore.entityTypes: string[]`
  - Toggle (StreamingMode) → `useChatStore.streaming: boolean`
  - Radio (ChunkingStrategy) → `useIngestStore.strategy: 'fixed' | 'semantic' | 'hybrid'`

#### UI 参数（来自 UI_PROMPTS §02-F）

Checkbox（16 × 16，radius 4）：
| 状态 | 背景 | 边框 | 标记 |
|---|---|---|---|
| default | #FFFFFF | 1 border-default #E5E5E2 | — |
| hover | #FFFFFF | 1 brand-400 #6A60E8 | — |
| checked | brand-500 #4F46E4 | — | 白色勾 stroke 1.5 |
| indeterminate | brand-500 | — | 白色横线 |
| disabled | bg-muted #EAEAE5 | — | text-tertiary 勾 |

Radio（16 × 16 圆）：
| 状态 | 背景 | 边框 | 内点 |
|---|---|---|---|
| default | #FFFFFF | 1 border-default #E5E5E2 | — |
| hover | #FFFFFF | 1 brand-400 #6A60E8 | — |
| checked | #FFFFFF | 1.5 brand-500 #4F46E4 | brand-500 圆点 6 × 6 |
| disabled | bg-muted #EAEAE5 | — | text-tertiary 点 |

Toggle / Switch（32 × 18 pill）：
| 状态 | Track 背景 | Thumb 背景 | Thumb 位置 |
|---|---|---|---|
| off / default | bg-muted #EAEAE5 | #FFFFFF | 左 |
| off / hover | text-tertiary #9A9A95 | #FFFFFF | 左 |
| on / checked | brand-500 #4F46E4 | #FFFFFF | 右 |
| disabled | bg-subtle #F4F4F2 | bg-canvas #FAFAF9 | — |

| 类别 | 值 |
|---|---|
| Label 字体 | Inter body-sm 13/15.7 text-primary，位于控件右侧（必须 `<label for>`） |
| 焦点环（共用） | `0 0 0 3px rgba(79,70,229,.20)` |
| 动效 · Checkbox 勾画 | 120 ms ease-out（stroke-dasharray 反推） |
| 动效 · Radio 内点 | spring scale 0→1 |
| 动效 · Toggle 圆球 | 200 ms ease-out translate；底色同步 fade |
| 键盘 | Space 切换；Tab 进入；Arrow 在 radiogroup 内切换（roving tabindex） |
| Toggle role | `switch`（**不是** checkbox） |

> 与 UI_PROMPTS 冲突，已按 FRONTEND_DESIGN_SPEC.md 修正：Checkbox/Radio 边框 `border-default #D3D3CE → #E5E5E2`；Toggle disabled 底 `#F4F4F1 → #F4F4F2`；hover 描边色取 `brand-400 #6A60E8`（SPEC 独有 token）。

---

## 总结 — 本批最值得固化的 3 条交互规范

> 为什么要列出来？因为这些规范在 LLM 长尾任务里反复被打破，必须 ESLint / 设计评审 / PR template 三重防线。

### ① Focus ring 必须 3 px brand-500/20，禁止 `outline: none` 不补
**为什么会被打破**：LLM 经常直接抄某个 npm UI 库的样式，那库默认 `outline:none` 后只补 `border-color`。结果键盘用户在 RAG-KG 这种全键盘科研工具里完全迷失。
**强制方式**：UnoCSS shortcut `focus-ring`；ESLint 规则 `vue/no-restricted-class` 拦截 `outline-none` 但不带 `ring-` 的组合。

### ② Disabled 必须切换到 `bg-subtle` + `text-tertiary`，禁止 `opacity-50`
**为什么会被打破**：opacity 是最快的"看起来 disabled"，但它会把 focus ring、shadow、文字 contrast 全部一起拉低，残障用户读不到，并且失去了"我能 hover 它告诉你为什么 disabled"的可能。
**强制方式**：BaseButton / BaseInput 的 disabled prop 在内部强制重写 style，不向外暴露 opacity prop；Stylelint `declaration-property-value-disallowed-list` 拦截 `opacity: <0.6` 与 button / input 选择器共现。

### ③ 数值徽章 / chunk_id / DOI / 引用编号必须 `font-mono tabular-nums`
**为什么会被打破**：LLM 默认走 sans 字体；但科研场景里 0.65 vs 0.85 用变宽字体跳动严重，引用 `[12]` 与 `[1, 2]` 对齐错位也会让 CitationChip 列表抖动。Cobalt Lab 已经在 Token 层把 mono 列为一等公民。
**强制方式**：UnoCSS shortcut `mono-num`；CitationChip / ConfidenceBadge / MetricCell 三个原子直接内嵌该 class，业务层调用方拿不到 override 入口。

### 风险点（最高优先级）
**CitationChip 使用 info-cyan 而非 brand-500 是 Cobalt Lab 的关键差异化决策**——它告诉用户"这是引用，是数据，不是交互按钮"。但这点在 token 表里只是 semantic info 的一种，**很容易被未来某个工程师误用 info 色到 Toast / Banner 上，从而稀释 Citation 的语义**。建议把 `info` token 重命名为 `citation-cyan` 并禁用于其他场景；Toast 的"信息"态另起一个 `neutral-info` 走 brand-100 浅底 + brand-700 文字，从根本上隔离两种"info"。
