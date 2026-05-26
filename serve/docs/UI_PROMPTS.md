# UI 提示词手册 — RAG-KG Copilot（Cobalt Lab 设计系统）

> 本文档把 `docs/PRD.md` / `docs/UI_UX.md` / `docs/FRONTEND_DESIGN_SPEC.md` / `docs/FRONTEND_RULES.md` 中的设计语言、信息架构、14 个 Figma Frame，以**最细颗粒度**拆解成可单独复制的"AI 生图 / UI 生成提示词"。
>
> **使用方式**：
> 1. 先复制 **§00 全局基底（Design System Preamble）** 作为每条提示词的前置上下文（让模型理解 Cobalt Lab 色板、字体、间距、圆角、阴影、动效）。
> 2. 再复制目标组件 / 页面 / Modal 的提示词，粘贴到 v0 / UX Pilot / Midjourney / Figma AI / GPT 图像 / Magic Patterns 等任意 UI 生成器。
> 3. 想得到一致的多图，建议**所有提示词共用同一 seed / style reference**，并明确指定屏幕宽 1440px / Modal 600–800px。
>
> **设计风格定位**：现代学术 SaaS（Linear × Notion × Arc Browser）；蓝紫学术主调 (Cobalt Indigo) + 暖灰中性 + 极高对比文本 + 克制语义彩色 + Inter / JetBrains Mono 字族。
>
> **设计原则一句话**：Citation-first / Library-aware / Progressive Disclosure / Long-task First-class / Trust through Trace / Keyboard-native。

---

## 目录

- [§00 全局基底（Design System Preamble — 必备前置）](#00-全局基底design-system-preamble--必备前置)
- [§01 设计系统总览（Tokens 频面）](#01-设计系统总览tokens-频面)
- [§02 基础原子组件（Atoms）](#02-基础原子组件atoms)
- [§03 领域组件（Domain Components）](#03-领域组件domain-components)
- [§04 主页面提示词（Screens S1–S8）](#04-主页面提示词screens-s1s8)
- [§05 Modal & Overlay 提示词（M1–M4）](#05-modal--overlay-提示词m1m4)
- [§06 系统态 / 边界态提示词](#06-系统态--边界态提示词)
- [§07 关键旅程串场提示词（J1 / J2 / J3）](#07-关键旅程串场提示词j1--j2--j3)
- [附录 A — Component → Screen 映射速查表](#附录-a--component--screen-映射速查表)
- [附录 B — 复制提示词时的注意事项](#附录-b--复制提示词时的注意事项)

---

## §00 全局基底（Design System Preamble — 必备前置）

> **⚠️ 每条单独的组件 / 页面提示词都必须把这一段贴在最前，确保 AI 在同一个设计语言里出图。**

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.
```

---

## §01 设计系统总览（Tokens 频面）

> 用途：单独生成一张"Design Tokens — Cobalt Lab"频面页（对应 Figma `Tokens` frame，2960×1320），可作为整套提示词的视觉总封面。

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Design a single 2960×1320 "Design Tokens — Cobalt Lab" reference frame on bg-canvas #FAFAF9
with 64px padding. Compose six labeled token sections in a left-to-right, top-to-bottom grid:

1) NEUTRALS · warm gray
   Title "NEUTRALS · warm gray" in meta 11/13.3 500 uppercase, color text-tertiary.
   Below it, a 6-cell row of 120×100 swatches (radius 14, shadow-sm) showing:
   bg-canvas #FAFAF9, bg-surface #FFFFFF (with thin border-subtle #E4E4E0),
   bg-subtle #F4F4F1, border #D4D4CE, text-secondary #525252, text-primary #1A1A1A.
   Each swatch has a label underneath in body-sm: token name on line 1, hex (mono) on line 2.

2) BRAND · cobalt indigo
   Title "BRAND · cobalt indigo".
   5 swatches 120×100: brand-50 #EDF0FF, brand-100 #DCE2FF, brand-300 #8D9FFF,
   brand-500 #4F46E4, brand-700 #2A1FAF. Same label pattern.

3) SEMANTIC · status
   Title "SEMANTIC · status". 4 swatches (500 only): success #10B881,
   warning #F59E0A, danger #EE4444, info #06B6D3.

4) KG ENTITY · 6 types
   Title "KG ENTITY · 6 types". 6 swatches: Concept #4F46E4, Method #10B881,
   Dataset #F59E0A, Metric #06B6D3, Author #A854F7, Venue #EB4799.
   Under each swatch, render a sample entity chip — a tiny colored dot + the
   type name in body-sm 600.

5) TYPOGRAPHY · Inter / JetBrains Mono
   A column with a live type ladder: display "Aa 36", h1 "Aa 28", h2 "Aa 22",
   h3 "Aa 20", body-lg "The quick brown fox 16/22", body "14/16.9",
   caption "12/14.5", meta "META · 11/13.3 UPPERCASE", and mono "chunk_2871 · doi:10.18653 · 13/20".
   Each row labelled with its token name on the right in text-tertiary.

6) SPACING · RADIUS · SHADOW
   Three small visual ladders:
   - Spacing: stacked horizontal bars 4/8/12/16/20/24/32/40/48/64 px, with px labels.
   - Radius: six rectangles 80×60 with corners 6 / 10 / 14 / 20 / 999, labeled.
   - Shadow: three white tiles 200×120 demonstrating shadow-sm / shadow / shadow-lg, labeled.

Title at the top of the frame: "Design Tokens — Cobalt Lab" h1 28/33.9 700 text-primary,
plus a subtitle in body 14/16.9 text-secondary: "Color · Typography · Spacing & Radius
· Shadow · KG entity types".

No mock screens, just a calm, well-aligned design-system reference page.
```

---

## §02 基础原子组件（Atoms）

> 12 个原子组件 + 若干补充原子。每个原子提示词都是**单图 / 多变体并排**形式，可贴到 v0 / UX Pilot 直接出 spec sheet。

### 02-A BaseButton（按钮）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Render a button spec sheet on bg-canvas. Component name "BaseButton". Show a 5×4 matrix:

Columns (5 variants):
1) Primary — bg brand-500 #4F46E4, text #FFFFFF, no border.
2) Secondary — bg bg-surface, text text-primary, 1px border border-default #D3D3CE.
3) Ghost — transparent bg, text text-primary, no border; hover fills bg-subtle.
4) Danger — bg danger-500 #EE4444, text #FFFFFF.
5) Link — no bg, text brand-600 #3B30D9, underline on hover.

Rows (4 states):
A) Default
B) Hover — primary -> brand-600; secondary -> bg-subtle; ghost -> bg-subtle; danger -> #D33A3A.
C) Active / Pressed — primary -> brand-700; subtle inner shadow.
D) Disabled — text-disabled #BDBDB8, bg neutral, cursor not-allowed.

Plus a row of sizes: sm 32h padding 8/12 text body-sm; md 40h padding 10/16 text body;
lg 48h padding 12/20 text body-lg. All radii radius=10.

Include focus state on one of them: shadow-focus ring 3px rgba(79,70,229,.2).
Show one with a leading Lucide icon "arrow-right" (16, stroke 1.5) on the right.
Show one "Loading" with a tiny spinner replacing the icon.

Label every cell with caption "<variant>/<state>" in text-tertiary, mono.
```

### 02-B BaseInput（单行输入）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseInput spec on bg-canvas. Width 360px, height 44px, radius 10,
1px border border-default #D3D3CE, bg bg-surface, padding 12/14,
text body 14/16.9 text-primary, placeholder text-tertiary #8C8C82.

Show 6 states stacked vertically with 24px gap:
1) Empty + placeholder "graphrag-survey".
2) Filled — value "graphrag-survey", caret bar at end.
3) Focused — border brand-500, plus shadow-focus 3px ring.
4) Error — border danger-500, helper text below in danger-700 body-sm
   "Slug must be 3–30 chars, lowercase/digits/hyphens only."
5) Disabled — bg bg-subtle, text-disabled.
6) With prefix/suffix — left icon "search" (Lucide, 16, text-tertiary), right hint kbd "⌘K"
   inside a 24×20 chip bg-subtle.

Above each input show a label "Library ID · slug" in meta 11/13.3 500 uppercase text-tertiary
with 4px margin. Below each, helper text in caption text-tertiary.
```

### 02-C BaseTextarea（多行输入）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseTextarea spec. 360×120, radius 14, border-default. Auto-resize behavior labeled.
Show: empty with placeholder "Description — what this Library is for…",
filled with 3 lines of body text, focused (brand-500 ring), and error variant.
Bottom-right of the textarea: a 12/14.5 caption counter "284 / 500" text-tertiary.
```

### 02-D BaseSelect（下拉选择）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseSelect spec. Trigger 280×36, radius 10, border-default, bg bg-surface.
Trigger content: leading dot (12×12 round, brand-500), label "graphrag-survey" body 14,
trailing caret "▾" 12px text-tertiary, padding 8/12.

Show OPEN state: trigger with brand-500 border + popover panel below, 280px wide,
radius 14, bg bg-surface, shadow-lg, padding 4, with 5 option rows 36h each:
- Active item bg brand-50, text-primary, leading dot brand-500.
- Hover item bg bg-subtle.
- Each item has 12×12 colored dot, then slug, then in mono caption "2,184 docs".
Bottom of the popover, a sticky row: "+ New Library" with leading plus icon
brand-600, body-sm 600.
```

### 02-E BaseSlider（滑杆）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseSlider spec. Track width 232, height 4, radius pill, bg bg-muted #EAEAE5;
fill brand-500 from 0 to thumb; thumb 16×16 round white, border brand-500 1.5,
shadow-sm. Above the slider, label "DEPTH · k-hop neighborhood" in meta 11/13.3 500.
Below the track, three tick marks "1-hop   2-hop   3-hop" in caption text-tertiary.
Render 4 examples stacked: depth=1, depth=2 (active), depth=3, and a confidence slider
with label "CONFIDENCE ≥ 0.65", value pill on the right showing "0.65" in mono.
```

### 02-F Checkbox · Radio · Toggle

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


A small spec card showing:
- Checkbox 16×16 radius 4, unchecked: white bg + border-default. Checked: brand-500 bg,
  white check icon. Disabled: bg-muted.
- Radio 16×16 circle, brand-500 ring + dot when selected.
- Toggle 32×18 pill, off bg-muted thumb white; on brand-500 thumb white, animates 120ms.
Use Inter body-sm label to the right of each. Group them in a 3×3 grid with state
captions ("default / hover / checked / disabled").
```

### 02-G BaseCard（卡片）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseCard spec. Two variants side by side, 320×180 each, radius 14, bg bg-surface:
1) bordered — 1px border-subtle #E4E4E0, no shadow.
2) elevated — no border, shadow-sm (default), shadow-md on hover.
Both share padding 20 with a header (h3 20/24.2 600), meta (caption text-tertiary),
divider 1px border-subtle, body slot (3 lines body), and footer with a ghost button "Open ↗".
```

### 02-H BaseBadge（徽章）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseBadge spec. 9 tones × 3 sizes grid.
Tones: neutral (bg bg-subtle, text text-secondary), brand (bg brand-50 text brand-700),
success (bg success-50 text success-700), warning (bg warning-50 text warning-700),
danger (bg danger-50 text danger-700), info (bg info-50 text info-700),
+ KG: concept, method, dataset, metric, author, venue (each bg <type>/50 mixed, text <type>/700).
Sizes: sm 18h text mono-sm 10/12.1; md 22h text meta 11/13.3; lg 28h text body-sm.
Radius 6 (radius-sm). Each badge can optionally start with a 6×6 round dot of its tone.
Examples: "● Healthy" success, "◐ Indexing" brand, "⚠ Stale community" warning,
"⊘ Failed" danger, "● Concept" KG concept.
```

### 02-I BaseChip（带关闭的胶囊）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseChip spec. 28h pill, radius 6 (radius-sm), bg neutral (bg-subtle), text body-sm 13/15.7,
text-secondary. Optional leading 12×12 dot, trailing "×" icon 12 stroke 1.5.
Variants: brand (bg brand-50 text brand-700), KG types, "selected" state with
brand-500 border. Show hover (background +1 step), close icon hover (text-primary).
```

### 02-J BaseTag（用于元数据 inline）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseTag — flat tag without bg, 20h, padding 0/6, text meta 11/13.3 500 text-tertiary,
optional uppercase. Used inline within metadata lines like
"Edge et al. · 2024 · Microsoft Research". Show 4 examples in a single row, separated by
the middot character.
```

### 02-K BaseModal（模态）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseModal frame spec. Container 600×640, radius 20 (radius-xl), bg bg-surface,
shadow-lg, centered above a backdrop rgba(15,15,20,.40) covering full viewport.
Inside, vertical layout, 32 padding:
- Header row 56h: title h2 22/26.6 700 text-primary on the left, close "×" icon 20
  text-tertiary on the right.
- Body slot (variable height) with 24 spacing between fields.
- Footer row 56h aligned right: Secondary "Cancel" + Primary action separated by 12.
Show focus trap by drawing a brand-500 focus ring on the Primary button.
Animation note: enters with 200ms ease-out, 8px Y translate.
```

### 02-L BaseDrawer（抽屉）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseDrawer spec. Slides from right, width 360 (small) / 440 (medium) / 800 (large).
Full viewport height. bg bg-surface, 1px left border-subtle, no radius on the attached side,
radius 14 inset on far-edge corners optional. Internal padding 24. Header row 64h with
title h3 20/24.2 600, secondary close "×" icon, optional kebab "⋯" menu.
Below: scrollable content area with sticky footer 64h if actions exist.
Show ARIA cues: aria-modal=true, focus trap, ESC closes.
```

### 02-M BaseTooltip · 02-N BasePopover

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseTooltip: floating 8px above element, max 240w, radius 8, bg #1A1A1A (text-primary)
with text in body-sm 13 text-inverted #FFFFFF; arrow 6×6 chevron; padding 8/10.
Appears 240ms after hover, dismiss 120ms.

BasePopover: like Tooltip but light: bg bg-surface, 1px border-subtle, radius 14,
shadow-md, padding 16, max-w 320. Used for CitationChip hover preview and document
failure popovers. Title body 14 600 + body-sm secondary.
```

### 02-O BaseEmptyState

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseEmptyState spec. Centered column. Above the fold:
- 40×40 round icon container bg bg-subtle, holding a Lucide icon (e.g. "inbox", "search-x",
  "alert-triangle") text-tertiary stroke 1.5 size 20.
- Title h4 18/21.8 600 text-primary, 16px margin top.
- Description body 14/22 text-secondary, max-w 360, center-aligned, 4px margin.
- Optional primary CTA button below.
Examples to render: "No documents yet — drop in PDFs to start indexing.",
"No evidence found in this Library. Try widening the year filter…",
"No path connects the two entities at depth ≤ 3."
```

### 02-P BaseSkeleton

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BaseSkeleton spec. Animated 1.2s pulse (mockup as a still). Variants:
- text-line: h 12px, radius 6, bg gradient from bg-muted to bg-subtle.
- avatar: 32 circle.
- card: 320×180 rect radius 14.
- KPI: 336×128 rect radius 14.
Show three skeletons stacked replicating the LibraryCard layout: title (60% width),
description 2 lines (90% / 70%), 4 stat numerals as small chips (50w each).
Note: only render after 800ms of pending state.
```

### 02-Q Toast（顶部右）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Toast spec. Width 360, radius 14, bg bg-surface, shadow-lg, 1px border-subtle,
padding 12/16, internal layout: 20-size status icon (left) + content (title body-sm 600,
description body-sm text-secondary) + close icon (right).
4 status flavors via left-edge accent bar (4px wide): success (success-500),
warning (warning-500), danger (danger-500), info (brand-500).
Anchor: top-right of viewport, 24 from edges, stack vertically 12 gap.
Auto-dismiss 5s; hovered: pause; aria-live=polite.
Examples: "Ingest started · 124 PDFs queued.", "Stream interrupted. Retry?",
"Review generated · Open task ↗".
```

### 02-R Avatar

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Avatar spec. Round 32×32 default (also 24 and 40). bg generated from initial hash
(use the brand/violet/pink/cyan tones in muted -50). Text: single initial, Inter 600
text-primary, center. Optional 8×8 status dot at bottom-right (success/danger).
Examples: "T", "G", "MK". Always include 1px subtle ring on hover for affordance.
```

### 02-S Tabs

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Tabs spec. Underline tabs aligned to a 1px bottom border-subtle. Each tab pill 40h,
padding 0/16, text body-sm 600. Active: text text-primary, 2px brand-500 underline,
no bg change. Inactive: text text-tertiary, hover -> text-secondary.
Show 4 examples in a row: "Overview · Documents · Knowledge Graph · Settings",
with second one active. Include keyboard cue: arrow keys cycle, Home/End jump.
```

### 02-T Divider

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Divider spec. 1px border-subtle horizontal full-width. Subtle inset variant: 1px gradient
fading to transparent at ends, used inside cards. Vertical divider 1px h:24, vertical-align
middle, used in inline meta rows.
```

### 02-U Progress Bar & Ring

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Progress spec.
- Linear: track 100% width × 4h, radius pill, bg bg-muted, fill brand-500;
  determinate value example 62%. Variant indeterminate: 30%-wide segment that animates
  left-to-right 1.4s ease-in-out infinite.
- Ring: 16 / 20 / 24 px diameters. stroke 2, brand-500 arc on bg-muted track.
  Indeterminate version: rotating 1s linear.
- Tiny inline progress (used in document rows): 88×3 radius 999, fill brand-500.
- Each progress paired with caption like "70%" or "step 4 of 7 · 04:18 elapsed · ~03:30 left".
```

### 02-V Status Pill（领域级，但归入原子）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


StatusPill spec. 22h pill, radius pill (999), padding 0/8, text mono-sm 11/13.3 600.
Layout: leading status glyph (●/◐/⚠/⊘) + label. 6 variants:
- "● Healthy" — bg success-50 text success-700, dot success-500.
- "◐ Indexing" — bg brand-50 text brand-700, dot brand-500.
- "◐ Parsing" — bg brand-50 text brand-700 (same family).
- "● Ready" — bg success-50 text success-700.
- "⚠ Stale community" — bg warning-50 text warning-700.
- "⊘ Failed" — bg danger-50 text danger-700.
- "● Running" — bg info-50 text info-700, dot info-500 pulsing.
Render the 6 pills in a row separated by 12.
```

### 02-W IconButton

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


IconButton 32×32 squircle (radius 10), transparent bg, Lucide icon 16 text-tertiary.
Hover bg bg-subtle, icon text-primary. Active bg-muted. Disabled icon text-disabled.
Show examples: 🔔 (Notify), 🌐 (i18n), ⋯ (kebab), 🔍 (Search), ⤢ (Expand panel).
Each variant must have an aria-label and tooltip.
```

---

## §03 领域组件（Domain Components）

### 03-A TopBar（顶栏）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Design AppTopBar at 1440×56, fixed top, bg rgba(255,255,255,.85) backdrop-blur 12px,
1px bottom border-subtle. Internal padding 0/24, items vertically centered, 16-gap layout:

[Left cluster]
- Logo mark: 24×24 squircle brand-500 with white diamond glyph "◆"; followed 8px later by
  text "RAG-KG" in body 14 700 text-primary.
[Then 24px gap]
- LibrarySwitcher trigger (see 03-D) 240–280w × 32h.
- Breadcrumb optional: body-sm text-tertiary, e.g. "/ Chat / Session 2026-05-05".
  Separators are middot " / ".

[Right cluster, push to right edge]
- CmdK Search trigger 120×32 (see 03-F)
- IconButton "Notify" 32×32 with red dot 8 if unread
- I18nSwitcher 36×32 — "EN ▾"
- Avatar 32×32 (see 02-R)

Show 3 states: default, with breadcrumb, with unread notification dot.
Maintain consistent vertical baseline; all hover states fade in 120ms.
```

### 03-B SideNav（左侧导航）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Design SideNav at 240×844 (full-height minus topbar). bg bg-surface, 1px right border-subtle.
Internal padding 16. Layout:

- Group label "WORKSPACE" meta 11/13.3 500 uppercase text-tertiary, padding 8/8.
- Nav items 216×36 each, radius 10, padding 0/12, gap 8 inside item:
  leading 16 Lucide icon stroke 1.5, label body-sm 600 text-secondary.
  Active item: bg brand-50, text brand-700, leading icon brand-500, plus a 3×28 brand-500
  vertical accent rail at the left edge.
  Hover: bg bg-subtle. Items:
   "◇ Overview"  "◆ Chat" (active)  "◇ Documents"  "◇ Knowledge Graph"
- 16 space, then group "TASKS":
   "◇ Review generation"  "◇ Cross-paper reasoning"
   "◇ Hypothesize"  "◇ Evaluation"
- 24 space, then a 216×180 mini-stats card (see 03-C) pinned to the bottom.
- Collapse mode (64w): only icons visible, tooltip on hover showing label.

Use ◆ for active, ◇ for inactive (line icons). Show standard + collapsed in two side-by-side panels.
```

### 03-C SideNav Mini-Stats Card

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Mini-stats card 216×180, radius 14, bg bg-subtle, padding 16:
- Top row: small dot 8 brand-500 + Library slug "graphrag-survey" body-sm 600.
- 2-line body body-sm text-secondary: "2,184 docs · 62.4k chunks", "8,491 entities · 31.2k triples".
- 1px divider border-subtle.
- Footer link "Open Library settings →" body-sm 600 brand-600.
Tone is calm informational, not a CTA.
```

### 03-D LibrarySwitcher

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


LibrarySwitcher trigger 240–280 × 32, radius 10, bg bg-surface, 1px border-default,
padding 4/10. Internal: 12×12 colored dot (matches Library's hash color, default brand-500)
+ slug body-sm 600 text-primary + trailing caret "▾" 12 text-tertiary.

Hover: bg bg-subtle. Focus: brand-500 ring.

Open panel (popover, see 02-N): 320×420, radius 14, shadow-lg.
Sections:
1) Search input 36h with "🔍 Search libraries…" placeholder.
2) "PINNED" meta label, then 3 rows: dot + slug + tiny stats "2,184 docs"
   on the right in mono caption text-tertiary. Active row highlighted bg brand-50.
3) "RECENT" meta label, then 3 rows similar.
4) Divider, then a row "+ New Library" with plus icon brand-600 body-sm 600.

Keyboard hints in footer: "↑↓ navigate  ↵ open  ⌘N new".
```

### 03-E Breadcrumb

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Breadcrumb spec. Inline row, body-sm text-tertiary; the last (active) segment text-secondary 600.
Separator is " / " with 6px horizontal padding. Truncate middle segments with "…" if total >480px.
Example: "Workspace  /  graphrag-survey  /  Chat  /  Session 2026-05-05".
```

### 03-F CmdK Search Trigger

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


CmdK trigger 120–200×32, radius 10, bg bg-subtle, no border. Internal padding 0/10:
Lucide "search" 14 text-tertiary + placeholder "Search…" body-sm text-tertiary +
right-aligned kbd "⌘K" inside a 22×18 chip bg bg-surface 1px border-subtle text mono-sm 600.
Hover: bg bg-muted. Clicking opens the CommandPaletteOverlay (M3).
```

### 03-G NotificationBell

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


IconButton 32×32 with Lucide "bell" 18. Unread state: 8×8 round danger-500 dot at top-right,
inside a 12px halo bg-surface to create separation.
Click → opens a 360×420 popover (NotificationCenter) anchored under the bell:
- Header row body 14 600 "Notifications" + ghost "Mark all read" body-sm.
- List of notification rows 64h:
  20×20 status icon (success/info/warning/danger background tint) +
  title body-sm 600 + meta body-sm text-tertiary + relative time caption right-aligned.
  Unread row has 4px brand-500 left accent rail.
- Footer link "Open notification center →" body-sm 600 brand-600.
Example items:
 ✓ "Review generation completed — GraphRAG advances 2024–2025" · graphrag-survey · 14m
 ⓘ "Ingest finished — 124 papers added"             · drug-target-discovery · 2h
 ⚠ "Community rebuild · 47 communities (Leiden d=3) — stale"  · yesterday
```

### 03-H I18nSwitcher

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


I18nSwitcher: 36×32 ghost trigger. Content "EN ▾" body-sm 600 text-secondary.
Popover 120×96 radius 10 shadow-md: two rows "English" (active, leading ✓) and "中文" (Inactive).
Locale persisted to localStorage.
```

### 03-I CitationChip（★ 标志性组件）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


CitationChip is the signature element of the product. Numeric pill inline within prose.

Geometry: 26×20, radius 4 (chip-radius variant for inline density). bg info-50 #EBFDFF,
1px border info-500 #06B6D3 at 24% opacity, text info-700 #0E7490, font mono 11/13.3 700,
center-aligned. The bracket marks "[" and "]" are NOT drawn; just the number.

Render 4 examples inline within a sample paragraph body 14/22 text-primary:
"GraphRAG splits retrieval into two complementary modes. In local mode, the planner
expands from the matched entity[1]. In global mode, the system reads community-level
summaries[2]; this materially improves multi-hop recall on tasks like MultiHop-RAG[3]."

States:
- default
- hover: bg info-100 (lighten), cursor pointer, plus a floating preview card
  appears 240ms later — see 02-N popover. Preview card content (320×140):
   • title body-sm 600 truncate 2 lines
   • meta caption "Edge et al. · 2024 · Microsoft Research"
   • 1px divider
   • quote: a 3-line excerpt, body-sm text-secondary, italic, with the matched terms
     highlighted in a warning-50 background.
- active / clicked: bg info-100, plus a brand-500 outline; main effect = scrolls the
  EvidencePanel on the right to corresponding card.
- focused (keyboard): shadow-focus ring.

a11y: role=button, aria-describedby points to the corresponding evidence card id.
Render all four states side by side.
```

### 03-J EvidenceCard

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


EvidenceCard 392×196, radius 14, bg bg-surface, 1px border-subtle, padding 16, gap 8.
Top row: CitationChip (26×20 info-styled) + title h4 18/21.8 600 max 2 lines.
Meta row: caption text-tertiary "Edge et al. · 2024 · Microsoft Research".
Quote block: body-sm text-secondary inside a 1px dashed border-subtle box with 12 padding,
3 lines max, italic; matched terms highlighted bg warning-50.
Footer row: mono caption text-tertiary with up to 3 metadata pills separated by middot:
 "vector · score 0.91", "p. 4 §3.2", "chunk_28a3" (the score in mono-sm 600 brand-700).

Variants per source:
- vector — small icon "axis-3d" Lucide 14 text-tertiary.
- bm25 — icon "type".
- graph — icon "git-branch".
- community — icon "users".

Hover: shadow-sm. Selected (linked to active citation): brand-500 1px border + brand-50 left
4px accent rail.
```

### 03-K EvidencePanel

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


EvidencePanel docked right, width 440 (full Chat) or 360 (KG view) × full height under topbar.
bg bg-surface, 1px left border-subtle, padding 24, gap 16. Header:
- h3 20/24.2 600 "Evidence"
- meta caption text-tertiary "3 sources cited · click [n] in answer to jump"
- collapse toggle icon "panel-right-close" right-aligned.

Body: vertical list of EvidenceCards (03-J) with 16 gap, scrollable.

Collapsed state: 56px rail with just the "panel-right-open" icon and a vertical mini-strip of
3 small dots indicating cited source count.

When the user clicks a CitationChip in the message, the corresponding card animates a 240ms
brand-50 wash + smooth-scrolls into view.
```

### 03-L MessageBubble — User vs Assistant

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Render two message blocks stacked, 712 wide.

USER MESSAGE: 28 avatar (round, bg brand-50, text brand-700 600 "T") on the left.
Right side: name "You" body 14 600 + relative time caption text-tertiary.
Below name: content in body 14/22 text-primary, no bubble background — flush text in a
soft container with 8px padding-left to align with the avatar.

ASSISTANT MESSAGE: same layout, but avatar is brand-500 with white diamond glyph "◆".
Name "RAG-KG · Claude Haiku 4.5" body 14 600.
Content rendered as native Notion-like paragraphs (no bubble), body 14/22 text-primary,
with inline CitationChips (03-I) where claims occur.
Streaming variant: trailing caret — a 2×16 brand-500 vertical bar that blinks 1Hz.
Below the message, a row of small actions in body-sm text-tertiary, separated by middot:
  "▾ Show reasoning trace · 6 retrieval steps · 4.2s"     (toggle)
  "Copy"   "Regenerate"   "Helpful 👍 / 👎"
```

### 03-M ReasoningTrace Toggle

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Reasoning trace, collapsed: a single ghost row "▾ Show reasoning trace · 6 retrieval steps · 4.2s"
body-sm text-tertiary.
Expanded: an indented panel left-bordered with a 2px brand-200 vertical rail, padding 12.
Each step is a row with:
 - 20×20 step number circle bg bg-subtle text body-sm 600 text-secondary.
 - Step title body-sm text-primary "Retrieve · vector top-K=12 in graphrag-survey".
 - Stats mono caption text-tertiary "412 tok · 1.2s · score 0.91".
Step types alternate icons (Lucide): "compass" (plan), "search" (retrieve), "filter" (rerank),
"sparkles" (synthesize), "check" (verify).
6 steps total. Last row "Synthesize answer · 1,824 tok · 2.1s".
```

### 03-N Composer（聊天输入区，★）

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Composer sticky at bottom of Chat column, 712w × auto (min 112h, max 224h), radius 14,
bg bg-surface, shadow-md, 1px border-subtle, padding 12/16.

Layout: top — a single multi-line textarea, no border, body 14/22 text-primary,
placeholder text-tertiary "Ask anything in this Library…    type "/" for commands".

Bottom row 36h, split into left cluster and right cluster:
LEFT:
- Library Pill 152×28 radius pill (999): bg brand-50, text brand-700, leading dot brand-500,
  body-sm "● graphrag-survey". Non-editable (visual constraint reminder).
- Model selector body-sm 600 text-secondary with caret: "Claude Haiku 4.5 ▾".
- Budget chip body-sm text-tertiary: "Budget · 8 steps · 32k tok" (click to adjust).
RIGHT:
- Slash hint pill body-sm text-tertiary "/" (clickable, opens commands).
- Primary Send button 72×32 radius 10 bg brand-500 text white "⌘↩ Send" body-sm 600.
  Disabled when empty; loading variant shows tiny spinner.

When user types "/", show a popover above the textarea (anchored bottom-left, 320×220, radius 14,
shadow-lg) listing slash commands:
"/review <topic>"  "/reason <question>"  "/hypothesize <e1>, <e2>"  "/clear"  "/rerank-on".
Each command row has a leading 16 icon, name in body-sm 600, and a body-sm text-tertiary description.

Empty state above the composer (when no messages yet): three example question chips horizontally
in bg-subtle, radius pill, body-sm: "How does GraphRAG combine local & global?" etc., clickable
to fill the composer.

Budget-exceeded banner (when over limit): a 32h danger-50 banner above the composer reading
"Budget exceeded. Increase or simplify the question." with a small "Adjust budget" link.
```

### 03-O SessionList Item

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Recent sessions list in the left sidenav or chat side rail. Each row 216×40, padding 0/12, radius 8,
hover bg bg-subtle. Layout: leading 12 icon "message-square" text-tertiary; title body-sm truncate
1 line text-primary; trailing caption text-tertiary right-aligned with relative time ("now", "14m",
"3 days").
Active session: bg brand-50, text brand-700, plus 3×28 brand-500 accent rail at left edge.
Section header "RECENT SESSIONS" meta uppercase text-tertiary on top.
```

### 03-P KG Canvas

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


KG canvas 800×844, radius 14, bg bg-surface, 1px border-subtle, padding 24. Above the graph,
a title row: h3 "Knowledge graph · graphrag-survey" + right-aligned toolbar icons
("fit" — fit to view, "rotate-ccw" — reset, "image-down" — export PNG, "code" — export JSON).

Render a force-directed graph of ~10 nodes positioned organically, with thin curved edges
(1px border-subtle, 30% opacity), arrowheads 6×6 on the target side. Edge labels appear on
hover in body-sm text-tertiary.

Nodes (see 03-Q) of different types and sizes; one center node is highlighted as "selected"
(brand-500 ring, brand-50 inner glow).

Legend at the bottom-right corner: 6 dots + type names in body-sm caption, matching KG type
colors. View-stats caption at the bottom-left: "8,491 entities (top 50 shown) · 31,219 triples
· confidence ≥ 0.65".

A subtle 12% dot-grid pattern in bg-muted overlays the canvas for spatial reference.
```

### 03-Q KG Node

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


KG node spec. Pill shape, radius pill (999), bg <type>/50, 1px border <type>/500 at 50% opacity,
text <type>/700, body-sm 600, padding 8/14. Variable width by label length, height 36–52 depending
on label lines. A leading 8×8 colored dot of <type>/500. Selected state: 2px brand-500 ring +
shadow-md. Hover: bg <type>/100. Disabled (filtered out): 30% opacity grayscale.

Variants:
- Concept (cobalt) "GraphRAG"
- Method (emerald) "Leiden algorithm"
- Dataset (amber) "MultiHop-RAG dataset"
- Metric (cyan) "Recall@10"
- Author (violet) "D. Edge et al."
- Venue (pink) "ACL 2025"
Render all 6 in a row at one common baseline.
```

### 03-R KG Edge

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


KG edge spec. 1px curved bezier line border-strong at 40% opacity by default; on hover,
the edge thickens to 2px and turns brand-500; an inline label appears at mid-arc on a
bg-surface chip radius 4 padding 2/6, text mono-sm 600 text-secondary, e.g.
"uses_method", "evaluates_on", "co_author_with". Direction arrow 8×8 chevron at the target.
```

### 03-S KG Filter Panel

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


KG filter panel 280×844 docked left, bg bg-surface 1px right border-subtle, padding 24, gap 24.
Sections:
1) Title "Filters" h3.
2) Search input 232×36 (see 02-B), prefix Lucide "search" 14, placeholder "🔍 Search entity…".
3) "ENTITY TYPES" meta uppercase. A 3×2 grid of toggleable chips (68×26 each) for the 6 KG types,
   each chip = colored dot + type name, radius pill. Active chip filled with <type>/50 +
   <type>/700 text; inactive chip bg bg-subtle text text-tertiary.
4) "DEPTH · k-hop neighborhood" meta. A BaseSlider (02-E) min=1 max=3 step=1, default 2.
5) "CONFIDENCE ≥ 0.65" meta + slider min=0 max=1 step=0.05.
6) "VIEW STATS" meta + 2-line body-sm text-tertiary: "8,491 entities (top 50 shown)" /
   "31,219 triples · confidence ≥ 0.65".
7) Footer ghost button "Reset filters" + secondary "Export view JSON".
```

### 03-T Entity Detail Drawer (in KG view)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


EntityDetailDrawer docked right, 360 wide, bg bg-surface, 1px left border-subtle, padding 24, gap 16:

- Type pill (BaseBadge KG variant) "● Concept" 76×26 radius pill.
- Title h2 22/26.6 700 "GraphRAG".
- "aka …" body-sm text-tertiary single line truncate: "aka  Graph-augmented RAG · KG-RAG ·
  Microsoft GraphRAG".
- Description body 14/22 text-secondary, 4 lines max.
- "NEIGHBORHOOD · 9 triples · 1-hop" meta. A vertical list of triple rows, each row 36h,
  mono body-sm 13: "— uses_method   →  Leiden algorithm". Hover bg bg-subtle, click jumps to
  that entity. 5 visible + "Show all 9 →".
- Primary button 312×44 "Ask about GraphRAG in Chat  →".
- "EVIDENCE · 47 chunks reference this entity" meta + a single sample quote (italic, body-sm,
  text-secondary) inside a 1px dashed box. Link "Show all 47 →" body-sm 600 brand-600.
```

### 03-U DropZone

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


DropZone full-width × 120h, radius 14, dashed 1.5px border-default, bg bg-canvas (slightly
darker than surface to invite drop), centered content:
- Big icon "upload-cloud" Lucide 32 stroke 1.5 text-tertiary.
- Title body-lg 16 600 text-primary "Drop PDFs, ZIPs, or folders here".
- Meta body-sm text-secondary "Files attach to graphrag-survey · parsing pipeline auto-routes
  to MinerU / Nougat".
- Help caption text-tertiary "or click "Upload PDFs" above · resumable, idempotent (SHA-256 dedupe)".

Hover / drag-over: border-strong brand-500 dashed 2px, bg brand-50 at 30% opacity, scale 1.01,
icon turns brand-500. Active-drop (file released): brand-500 progress bar across the bottom 3px.

Provide an alternate compact 380h drop area variant for the empty-Documents state.
```

### 03-V Document Row (in Documents table)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Document row inside a 1376w table. Row height 64, 1px bottom border-subtle.
Columns and their widths (with internal padding 0/16):

- TITLE (flex-1) — title body 14 600 text-primary 1-line truncate + meta caption text-tertiary
  below it "Edge et al. · Microsoft Research · arXiv:2404.16130".
- YEAR (72w, mono caption text-secondary, right-aligned numeric).
- STATUS (140w) — StatusPill (02-V): one of "● Ready" success, "◐ Indexing" brand,
  "◐ Parsing" brand, "⊘ Failed" danger. Below the pill, when in progress, an inline 88×3
  progress bar with mono caption "70%" next to it.
- CHUNKS (96w, mono 14/22 text-primary, right-aligned). When indexing not yet finished:
  "— / 96".
- ENTITIES (96w, mono 14/22). "—" when not finished.
- INGESTED (140w, body-sm text-tertiary) "3 days ago" / "just now · 32%".
- ACTION (40w) kebab "⋯" icon button.

Failed rows show a "↻ Retry with MinerU" small ghost link in the action area; clicking the
status pill opens a FailedErrorPopover (03-AQ) anchored to it.

Header row 48h, bg bg-subtle, text meta uppercase 11/13.3 text-tertiary, sortable indicators.

Show 5 example rows including all 4 statuses and an "X more rows" meta footer reading
"… 2,179 more docs" in caption text-tertiary, centered.
```

### 03-W Ingest Progress (per-doc)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


A per-doc progress strip used inline in the Documents table. 88w × 22h pill that combines:
- StatusPill leading "◐ Parsing" (text mono-sm 600).
- 88×3 progress bar below the pill (radius 999, fill brand-500 to value%, track bg-muted).
- Caption "2m ago · 70%" body-sm text-tertiary.

Animation: indeterminate variant uses a 30%-wide brand-500 segment sliding left→right 1.4s.
```

### 03-X DocumentDetailDrawer Sections

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


DocumentDetailDrawer 800×900 sub-sections to be implemented as reusable widgets:
- Stat group: 4 stat cells in a row, each 80w; numeral h2 22 700 + label caption text-tertiary
  ("128 chunks", "94 entities", "218 triples", "22 pages"). Tabular numerals.
- PDF preview: 336×408 placeholder card, radius 14, bg bg-subtle, 1px border-subtle, content
  centered: icon "file-text" 32 text-tertiary, mono caption "📄 page 1 of 22", label "PDF preview".
- SectionsList: vertical, each row 36h, mono caption text-secondary, hover bg bg-subtle:
  "1   Abstract", "2   Introduction", "3   Methods …". 12 rows.
- ChunksList: 3 example mini-cards 4px left brand-100 accent rail, body-sm content with
  mono "chunk_2871" prefix, then "§4.5 · p.4 ·  "...we observe that local search is
  appropriate…"" italic snippet.
- 3 action buttons in a footer row, gap 8: Secondary "↻ Re-parse" 152×40, Primary
  "Open in Chat / Ask →" 200×40, Danger ghost "Remove document" 152×40.
```

### 03-Y Pipeline Tree (TaskProgress)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


PipelineTree component, 280–320 wide. List of stages with parent / child indentation:

A stage row 56h: left rail vertical 2px brand-200 connecting siblings; a 20×20 round status
icon (filled ◉ done brand-500; spinning ◔ active brand-500; hollow ◯ pending text-tertiary;
✗ failed danger-500); title body-sm 600 text-primary; meta caption text-tertiary "412 tok
· 3.2s" right-aligned.

Substages indented +20 with same icon scheme. Active stage has a brand-50 wash over the whole
row. Last leaf may show streaming dots "writing…" with a 22ms blink cursor.

Example tree (used in Review):
◉  Decompose into subtopics         412 tok · 3.2s
◉  Subtopic 1: Pre-trained models
   ◉  Local search · 32 chunks
   ◉  Draft  ▌ writing…
◯  Subtopic 2: Hierarchical KG
◯  Citation cross-check

Below the tree, a 1px border-subtle divider, then a "RUN STATS" meta label and a 2-column
list with mono numerals: "Tokens used 14,328 / 32,000", "Cost so far $0.36", "Elapsed 04:18",
"ETA ~03:30".
```

### 03-Z Run Stats Sidebar (for long tasks)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


Run stats panel 320×784, radius 14, bg bg-surface, 1px border-subtle, padding 20. Header:
"Pipeline" h3 20 600 + meta body-sm text-tertiary "step 4 of 7 · 04:18 elapsed · ~03:30 left".
A "● Running" StatusPill 88×32 anchored top-right next to a "Run in bg ↗" link body-sm 600 brand-600.

Body: PipelineTree (03-Y) followed by RUN STATS block.

Footer (sticky bottom): two buttons 50/50 — Secondary "Cancel run" 130×40 danger-ghost, Primary
"↓ Download draft .md" 142×40 secondary.
```

### 03-AA Live Citation List

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


LiveCitationList 336×784, radius 14, bg bg-surface, 1px border-subtle, padding 20.
Header "Live citations" h3 + meta "29 unique sources · 0 broken · cross-checked" caption
text-tertiary.
Body: vertical numbered list, each item 64h: CitationChip 26×20 + title body-sm 600 truncate 2
lines + meta caption "Edge et al. 2024". Hover bg bg-subtle.
Footer link "+ 22 more →" body-sm 600 brand-600.

This list updates live as the review streams; newly added items briefly highlight bg brand-50
for 800ms.
```

### 03-AB Review Draft Streaming View

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


ReviewDraftStreaming 688×784, radius 14, bg bg-surface, 1px border-subtle, padding 32, gap 16.
Content is a long-form markdown render:
- h1 "GraphRAG advances 2024–2025" display 36 700.
- Meta line body-sm text-tertiary: "Draft  · 524 / 3,000 words  · 29 citations  · graphrag-survey".
- 1px divider.
- h2 sections "1. Pre-trained models for KG construction", "2. Hierarchical knowledge graphs", …
- Body paragraphs body 14/22 text-primary with inline CitationChips, e.g.
  "Recent work on GraphRAG has converged on GPT-class extraction[1]. Tu et al.[2] show that …".
- The currently streaming sentence appears with a blinking 2×16 brand-500 caret.
- Below the streaming paragraph, a one-line meta caption text-tertiary:
  "Drafting subtopic 2 · Haiku 4.5 · 324 / 800 tokens".
- After the streaming area, 1px divider, then a pending-section preview body-sm text-tertiary
  italic: "3. Community summaries  ⏵ pending\n4. Eval & limitations  ⏵ pending".

Empty state for 0-chunk subtopics: a soft warning-50 inline box body-sm warning-700 reading
"No chunks matched this subtopic. Try widening year filter or upload more papers."
```

### 03-AC Path Visualization (Reasoning)

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


PathVisualization 672×320, radius 14, bg bg-surface, 1px border-subtle, padding 24.
Title h3 "Best meta-path · 3 hops · confidence 0.78".
Center: a horizontal node-edge-node sequence on a single line, evenly spaced:
[Concept "GraphRAG" 112×52]  ─ "— uses_method →" body-sm text-tertiary  [Method "Community
summary" 152×52]  ─ "— extended_by →"  [Author "Tu et al. 2025" 128×52]  ─ "— evaluates_on →"
[Dataset "PrimeKG (biomedical)" 152×52].
Each node is a KG node (03-Q) in the appropriate type color.

Below the path: 1px divider, then "CONCLUSION" meta uppercase, then body 14/22 text-primary
multi-line conclusion, with inline CitationChips referencing supporting evidence.
```

### 03-AD Evidence Timeline

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


EvidenceTimeline 672×252, radius 14, bg bg-surface, 1px border-subtle, padding 24.
Title h3 "Evidence timeline · 4 papers across the 3 hops".
Body: 4 horizontally-arranged year columns on a continuous baseline (a 1px brand-200 vertical
center axis), each year is a dot 12×12 brand-500 with caption "2024-04" / "2024-09" / "2025-03"
/ "2025-08". Under each dot, a small EvidenceCard variant 152×96: author + quote excerpt + chip
chunk_id.
Footer CTA: ghost "Open all 4 in Chat  →" body-sm 600 brand-600.
```

### 03-AE Hypothesis Card

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


HypothesisCard 656×180, radius 14, bg bg-surface, 1px border-subtle, padding 20, gap 12.

Top row: leading rank pill 36×22 radius pill bg brand-500 text white body-sm 600 "#1";
title text 4-line max body 14/22 text-primary, ending with inline CitationChips for support.

Middle: 3-column meter row, each col 120w:
- Label meta text-tertiary uppercase ("novelty", "confidence", "verifiability").
- Track 120×4 radius pill bg bg-muted, fill brand-500 to value%.
- Value mono 600 13 right-aligned ("0.85", "0.72", "0.78").

Footer caption text-tertiary: "3 supporting paths in KG · grounded in 4 papers · 12 chunks".

Compact variant 656×88: rank + 2-line text + meta meters inlined.

Selected card: 2px brand-500 outline + brand-50 left 4px rail.
```

### 03-AF KPI Card

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


KPI card 336×128, radius 14, bg bg-surface, 1px border-subtle, padding 20.
Layout: label meta uppercase text-tertiary on top (e.g. "VAR · Valid Answer Rate"); large value
h1 28/33.9 700 text-primary mid-left ("76.4%"); delta chip body-sm with arrow + colored bg
(positive = success-50 success-700, negative = danger-50 danger-700) on the right of the value:
"↑ 2.1pp / week".
Bottom line body-sm text-tertiary: "target ≥ 75% · v1.0 GA criterion · ✓ on track".

Render 4 KPI cards in a row: VAR, Citation F1 (0.872, ↑0.04/week, target ≥0.85),
P95 latency (14.2s, ↓1.8s/week, target ≤20s), $/question (0.084, ↓$0.012/week, target ≤$0.10).
All deltas use ↑/↓ arrows in 600 weight.
```

### 03-AG Trend Bar Chart

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


TrendBarChart 864×280, radius 14, bg bg-surface, 1px border-subtle, padding 24.
Title h3 "VAR · daily · last 30 days".
Meta body-sm text-tertiary "smoke set · 10-question rolling window · target line at 75%".

Chart area: ~12 vertical bars 56w each, evenly spaced, heights vary 60–180. Bars use a
brand-500 fill with subtle linear gradient to brand-300 at the top.  Hovered bar: brand-700.
A 1px dashed warning-500 horizontal "75%" target line crosses the chart with a small label
"75%" at the right edge.

X-axis labels caption text-tertiary "May 1   May 8   May 15   May 22   May 29" evenly spaced
under the bars. No Y-axis ticks; instead, two faint horizontal gridlines at 50% and 100% in
border-subtle.

Below the chart, a small "● this week" + "○ last week" legend, body-sm caption text-tertiary.
```

### 03-AH Failure Case Table

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


FailureCaseTable 864×248, radius 14, bg bg-surface, 1px border-subtle, padding 20.
Title h3 "Recent eval failures · click to inspect trace in Langfuse".

Header row 36h, mono caption text-tertiary uppercase:
"QID   SET   QUESTION (truncated)   FAILURE   VAR Δ   COST".

Each data row 48h, hover bg bg-subtle, body-sm text-primary, mono numerals. 4 rows shown,
e.g. "multihop-027  multihop  Did GraphRAG outperform…  citation_invalid  -1.0pp  $0.12".

Failure reason rendered as a danger-50 chip with danger-700 text body-sm.
Last row "View all 14 failures in Langfuse →" body-sm 600 brand-600.
```

### 03-AI Alert Banner

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


AlertBanner 1376×40 (full width inside container). 4 tones: success / info / warning / danger.
Layout: 16-pad row, leading status icon 20, content body-sm 600 first sentence + body-sm
text-secondary detail, trailing dismiss "×" icon.

Examples:
- Success: bg success-50, text success-700, "● All KPIs within target · last alert 9 days ago".
- Warning: "⚠ Citation F1 has dropped 0.04 over 7 days — inspect failures".
- Danger:  "⊘ Ingest worker offline — uploads queued, will retry on reconnect".
- Info:    "ⓘ New eval set 'multihop-v3' published. Run via Settings → Evaluation.".
Sticky to the top of /eval main column under the page header.
```

### 03-AJ Library Card

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


LibraryCard 320×220 (responsive min 300, max 1fr in grid), radius 14, bg bg-surface, 1px
border-subtle, padding 20, gap 12, hover shadow-md.

Top row: name h3 20/24.2 600 text-primary on the left + StatusPill on the right
("● Healthy" / "◐ Indexing" / "⚠ Stale community").

Description body-sm 13/15.7 text-secondary, 2 lines clamp:
"GraphRAG, graph-based retrieval, and multi-hop reasoning across NLP venues 2023–2025."

Stats grid 4 columns:
- "2,184" h2 22 700 + "docs" caption text-tertiary
- "62.4k" + "chunks"
- "8,491" + "entities"
- "31.2k" + "triples"
Tabular numerals; even spacing.

Footer row body-sm text-tertiary "Last activity · 14m ago" + kebab "⋯" on the right.

"+ New Library" card variant: 320×220 with a dashed 1.5px border-default + bg-canvas;
content vertically centered: 64×64 round container bg bg-subtle with big "+" brand-600,
title body 14 600 "New Library", caption text-tertiary "Start a new research direction".
```

### 03-AK Recent Activity Item

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


RecentActivityItem (used in dashboard activity list). Row 56–72h, padding 12, gap 12.
Layout: leading 32×32 round icon container with a soft tint matching the action type
(success-50 + check icon, brand-50 + sparkles icon, warning-50 + alert-triangle).
Then a column:
 - Title body 14 600 text-primary truncate 1 line. Title may include a quoted artifact name
   in italic 600.
 - Meta body-sm text-tertiary middot-separated, e.g. "graphrag-survey · 3,142 words · 47
   citations".
Trailing caption text-tertiary right-aligned relative time "14m ago".
Hover bg bg-subtle radius 10.
1px horizontal divider between items, inset 12 from left.

Render 3 example items in the dashboard activity list (Review complete · Ingest finished ·
Community rebuild).
```

### 03-AL Quality KPI Panel

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


QualityKPIPanel 384×320 (or responsive 2×2 / 1×4 grid >=1024). radius 14, bg bg-surface,
1px border-subtle, padding 24, gap 16.
Title h3 "Quality at a glance".
Body: 4 small KPI rows or grid, each:
 - Label meta uppercase text-tertiary on top.
 - Value h2 22/26.6 700 text-primary.
 - Delta caption (↑/↓ with success/danger color).
Items: "Valid Answer Rate (VAR) 76.4% ↑2.1pp this week",
"Citation F1 0.872", "P95 latency 14.2s", "$ / question (avg) $0.084", "Recall@10 0.74".
Below: 1px divider, then a single caption text-tertiary "Targets · VAR ≥ 75% · Citation F1
≥ 0.85 · P95 ≤ 20s · $ ≤ 0.10".
```

### 03-AM LLM Router Picker

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


LLMRouterPicker. Trigger 272×32 select with a long composite label "Local Qwen2.5-32B  →
Haiku 4.5  →  Sonnet 4.6 ▾" in body-sm 600 text-primary; the arrows visualize the routing chain.
On open, popover 360×280: a vertical drag-handle list with 3 reorderable rows
(Local Qwen / Haiku 4.5 / Sonnet 4.6), each row 48h with a "grip-vertical" handle icon left,
model name + model size pill, and a toggle to remove. Below the list a single "+ Add model"
ghost row brand-600.
Footer: "Save" primary + "Reset to global default" link.
```

### 03-AN Embedder Picker

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


EmbedderPicker trigger 272×32 select with label like "BGE-M3  ·  4096 dim  ·  local ▾".
Popover lists 3 embedder options as radio rows:
- BGE-M3 (local, 4096) — recommended badge "Recommended" brand-50/700 chip.
- Voyage-3 (api, 1024)
- OpenAI text-embedding-3-large (api, 3072).
Each row shows name body-sm 600, sub caption text-tertiary, and a tiny "$" cost pill on the right.
```

### 03-AO Budget Settings Form

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


BudgetSettings form (inside Library settings panel). 448w. 5 rows, each row 48h:
label body-sm text-primary on the left + numeric input 96×32 on the right with unit suffix
("steps", "calls", "tokens", "$").
Rows:
- Max retrieval steps           [8]
- Max LLM calls                 [12]
- Tokens per question           [32,000]
- Daily cost cap                [$5.00]
- Per-question cost soft cap    [$0.20]
Section heading "BUDGET · per question" meta uppercase text-tertiary on top.
1px divider below the section.
```

### 03-AP Schema Editor

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


SchemaEditor — Monaco-lite. 696×384, radius 14, bg #0F1118 (dark editor surface — exception to
the light theme inside the editor only), 1px border-subtle. Top tab bar bg bg-subtle (light side)
with one tab "library.schema.yaml" + a "Reset to template" ghost link.
Editor body: line-numbered gutter text-tertiary mono 11, code in JetBrains Mono 13/20.
Use a calm syntax theme: keys in #8D9FFF (brand-300), strings in #10B881, numbers in #F59E0A,
comments in #515151.
Sample content:
  entity_types:
    - concept
    - method
    - dataset
  triple_confidence_min: 0.65
  rerank: bge-reranker-v2
Footer ghost link "Validate" + Primary "Save". Save shows a 24h success-50 toast at top of the
form.
```

### 03-AQ Failed Error Popover

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


FailedErrorPopover 320×144, radius 14, bg bg-surface, shadow-lg, 1px border-danger-500 at 20%,
padding 16, anchored above a failed StatusPill. Layout:
- Title row body-sm 600 danger-700 with leading "⊘" glyph: "⊘ Parse error".
- Body body-sm text-secondary 3 lines: "Nougat detected scanned image-only PDF. No text layer.
  Retry with MinerU OCR pipeline?"
- Two-button footer: ghost "Dismiss" + Primary "↻ Retry with MinerU".
Pointer/arrow 8×8 at the bottom-center.
```

### 03-AR Cost Meter

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:


CostMeter inline component used in run stats + composer. 240×32. Layout:
- Label meta text-tertiary "Cost so far".
- Mono value 14 600 text-primary "$0.36".
- 88×4 progress bar (radius 999) showing fraction used vs daily cap; fill color is brand-500
  when <60%, warning-500 60–90%, danger-500 ≥90%.
- Tiny caption text-tertiary right "$0.36 / $5.00 daily cap".
```

---

## §04 主页面提示词（Screens S1–S8）

> 每张主页面 1440×900，置于 #FAFAF9 画布上，TopBar 56h 固定顶部，左 SideNav 240w，自适应主区。

### S1. Onboarding — `/onboarding`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a 1440×900 marketing-grade Onboarding screen on bg-canvas #FAFAF9. No SideNav.
Center-aligned single-column hero, max-width 720, vertical rhythm 24.

Top-left fixed: 40×40 brand-500 logo squircle "◆" + 8 gap + "RAG-KG Copilot" body 14 700.
Top-right: I18nSwitcher "EN ▾".

Center stack (vertically centered with slight upward bias):

1) Hero title display 36/43.6 700 text-primary, single line:
   "Your private RAG-KG Copilot."

2) Subtitle body-lg 16/22 text-secondary, 2 lines:
   "Drop your PDFs into a Library. Ask questions. Get answers with verifiable citations and
   a knowledge graph — all self-hosted, no telemetry."

3) A row of 3 step cards, each 240×200, radius 14, bg bg-surface, 1px border-subtle, padding 24,
   gap 32 between cards:
   - "01"  display 28 700 brand-500
     "Create a Library"  h4 18 600
     "Each research direction lives in its own isolated namespace."  body-sm text-secondary
   - "02" "Drop your PDFs" "Parse, embed, and build a knowledge graph automatically — resumable
     and idempotent."
   - "03" "Ask with citations" "Every answer comes with verifiable evidence chips you can click
     to trace."

4) Primary CTA button 280×52 radius 10 bg brand-500 text white text body-lg 600:
   "Create your first Library  →"

5) Secondary ghost CTA below, body-sm 600 brand-600: "or  See a demo Library".

6) Trust line caption text-tertiary, centered:
   "No account needed · Self-hosted · Your data stays on your machine."

Background: a very faint dot-grid (3% opacity) bg-muted; do NOT use gradients or images.
Animation hint: hero title fades in 240ms, cards stagger 80ms, CTA pulses subtly 1× on mount.
```

### S2. Library Dashboard — `/libraries`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a 1440×900 Library Dashboard. Render full chrome:
- TopBar 1440×56 (see 03-A): logo + "RAG-KG", LibrarySwitcher (240×32 trigger showing first
  library), Breadcrumb hidden, CmdK trigger "Search… ⌘K", I18nSwitcher, NotificationBell with
  unread dot, Avatar "T".
- No SideNav (this is the global dashboard).

Main content padding 32:

1) Page title row:
   - h1 28/33.9 700 "Your Libraries" left
   - Right: Primary button "+ New Library" 144×40 bg brand-500.

2) Page meta below the title, body-sm text-tertiary:
   "3 active libraries · 4,872 documents · 142,108 chunks · 22,896 entities".

3) Library grid, 4 columns, gap 20:
   - 3 LibraryCards (03-AJ): "graphrag-survey" ● Healthy, "drug-target-discovery" ● Healthy,
     "neuro-causal-inference" ◐ Indexing.
   - + 1 "New Library" dashed card with plus icon.

4) 1px divider 32 above and 32 below.

5) Two-column 16:9 area below — left 896w "Recent activity" panel, right 384w "Quality at a
   glance" KPI panel:

   - LEFT: Section title h3 "Recent activity" + see-all link "See all →" right-aligned.
     Card bg bg-surface, radius 14, 1px border-subtle, padding 24. Inside, 3 RecentActivityItems
     (03-AK) with 1px subtle dividers between them.

   - RIGHT: QualityKPIPanel (03-AL).

6) Sticky footer-bar 1376×40 inside the content area: a Library status legend body-sm text-tertiary
   "Library status legend:" + 3 chips (Healthy / Indexing / Stale community), each chip 22h pill
   with leading symbol.

No images, no gradients. Use shadow-sm on cards, shadow-md on hover only.
```

### S3. ★ Chat / QA — `/lib/:id/chat`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose the flagship 1440×900 Chat screen. THREE-COLUMN layout:
- SideNav 240 (see 03-B), "◆ Chat" item active.
- Conversation center 760 (1440 - 240 - 440), padding 32.
- EvidencePanel 440 docked right (see 03-K).

TopBar (03-A) full width on top: logo + "RAG-KG", LibrarySwitcher "● graphrag-survey ▾",
Breadcrumb "/ Chat / Session 2026-05-05", CmdK trigger, NotificationBell, Avatar "T".

CONVERSATION CENTER (top-to-bottom):

Header block:
- Meta caption text-tertiary "Session · 2026-05-05 · 14:32".
- Session title h2 22/26.6 700 text-primary (one line): "How does GraphRAG combine community
  summarization and vector retrieval?".
- 1px divider border-subtle 680w.

Message stack (gap 24):

USER message (03-L user variant):
- Avatar 28 "T" brand-tinted.
- Name "You" body 14 600 + caption "14:32".
- Content body 14/22 text-primary, 3 paragraphs ending with a concrete query.

ASSISTANT message (03-L assistant variant), streaming:
- Avatar 28 brand-500 "◆".
- Name "RAG-KG · Claude Haiku 4.5".
- Content with multiple paragraphs and 3 inline CitationChips (info-cyan) [1] [2] [3].
- Trailing blinking caret right after the last token.
- Reasoning trace toggle below: "▾ Show reasoning trace · 6 retrieval steps · 4.2s".

Then the Composer (03-N), sticky to the bottom-right gutter of the center column, 712w × 112h
(min), with the empty bar showing placeholder "Ask anything in this Library…   type "/" for
commands".

EVIDENCE PANEL (03-K) on right:
- Header "Evidence" h3 + caption "3 sources cited · click [n] in answer to jump".
- 3 EvidenceCards 392×196 stacked, the first one slightly highlighted (linked to active citation).
  Use the spec examples (Edge 2024 GraphRAG; Liu 2025 Hierarchical Community Summaries; Cormack
  2009 RRF). Each card includes its [n] CitationChip in the top-left.

SIDENAV bottom: pinned RECENT SESSIONS section (03-O) with an active row "→  GraphRAG local vs
global   now", below it the mini-stats card (03-C).

Edge cases to visualize as small floating notes (sticky-note style, NOT real UI):
- Empty 0-hit retrieval shows a 396w EmptyState card replacing the right panel content reading
  "No evidence found in this Library. Try widening the year filter or upload more papers."
- Stream interrupted: red link "Stream interrupted. Retry" appears after the last token.

Use shadow-md on the Composer only. Everything else stays subtle and ink-like.
```

### S4. KG Browser — `/lib/:id/kg`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose 1440×900 KG Browser. THREE-COLUMN: SideNav 240 + KGFilterPanel 280 + KGCanvas 560 +
EntityDetailDrawer 360 (so center+right share remaining 920; canvas 560 / detail 360).

TopBar shows: "◆ RAG-KG ● graphrag-survey / Knowledge Graph".
SideNav with "◇ Knowledge Graph" active.

Render in order from left to right:

1) KGFilterPanel (03-S) docked at x=240, fully filled.
2) KGCanvas (03-P) centered. Force-directed layout with 10 entities arranged organically. A
   12% bg-muted dot-grid behind nodes. Center node "GraphRAG" (Concept type) is selected
   (2px brand-500 ring + brand-50 inner glow + shadow-md). 1–3 hop neighbors fan out around it.

   Show edges with labels appearing only on hover; for static design, label the 4 most
   important edges:
   - GraphRAG —uses_method→ Leiden algorithm
   - GraphRAG —uses_method→ Community detection
   - GraphRAG —uses_method→ Vector retrieval
   - GraphRAG —evaluates_on→ MultiHop-RAG dataset
   - GraphRAG —authored_by→ D. Edge et al.

3) EntityDetailDrawer (03-T) docked right, populated for GraphRAG.

Canvas toolbar (top-right of canvas): 4 icon buttons "fit / reset / export-png / export-json"
with tooltips.

Footer legend strip 24h at bottom of canvas: 6 colored dots + type names + a tiny caption "8,491
entities (top 50 shown)" left, and "31,219 triples · confidence ≥ 0.65" right.

Empty state variant: if 0 entities match the filter, replace canvas with EmptyState "No entities
match the current filters. Try lowering confidence to 0.5 or selecting more types."

A11y: provide a "List view" toggle in the canvas toolbar that swaps the canvas for a structured
list (off in default render but visible as a small toggle icon).
```

### S5. Review Generation (in progress) — `/lib/:id/review/:taskId`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose 1440×900 Review Generation IN-PROGRESS screen.
TopBar text "◆ RAG-KG ● graphrag-survey / Review · GraphRAG advances 2024–2025".
SideNav with "◇ Review generation" active.

Top-right of header: StatusPill "● Running" + small link "Run in bg ↗" body-sm 600 brand-600.

Main area three-column under topbar:
- Left: PipelineTree / Run stats panel 320×784 (03-Z).
- Center: ReviewDraftStreaming 688×784 (03-AB).
- Right: LiveCitationList 336×784 (03-AA).

Use 24 gap between columns; padding 24 inside the main area.

Pipeline tree shows 7 stages with step 4 active and streaming on subtopic 2:
◉ Decompose into subtopics (412 tok · 3.2s)
◉ Subtopic 1: Pre-trained models
  ◉ Local search · 32 chunks
  ◉ Draft · 612 tok
◔ Subtopic 2: Hierarchical KG
  ◔ Local search · 28 chunks (just completed)
  ◔ Draft · 324 / 800 tok  ▌ writing…
◯ Subtopic 3: Community summaries
◯ Subtopic 4: Eval & limitations
◯ Citation cross-check

RUN STATS block under the tree: Tokens 14,328 / 32,000, Cost $0.36, Elapsed 04:18, ETA ~03:30.

Footer of left panel: Secondary "Cancel run" 130×40, Primary "↓ Download draft .md" 142×40
(disabled until completion).

Center draft panel: shows h1 + meta + h2 sections with one subtopic fully written and another
mid-stream with a blinking caret. Inline CitationChips throughout. Below the streaming
paragraph, a meta line "Drafting subtopic 2 · Haiku 4.5 · 324 / 800 tokens". Below, a divider
and pending subtopics in italic text-tertiary.

Right panel: 6 visible citation rows; the most recently added (rows 5 and 6) glow brand-50 for
800ms.

Empty state note (rendered as a sticky annotation, NOT a UI element):
"When 0 chunks match a subtopic, render a warning banner instead of inventing content."
```

#### S5b. Review Configuration (pre-run) — `/lib/:id/review`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Configuration variant of Review screen, 1440×900. Same chrome, but the central area is a single
centered card 720×620, radius 20, bg bg-surface, shadow-md, padding 40.

Card content:
- h2 "Generate a literature review" + body-sm text-secondary "Configure scope, then estimate
  cost."
- 1px divider.
- "Topic" label meta + BaseTextarea 640×96 placeholder "e.g. Hybrid retrieval for biomedical
  knowledge graphs, 2024–2025".
- Two-column row:
  - "Year range" label + BaseSlider with two thumbs (2018 ←→ 2025) and value chip "2024–2025".
  - "Target length" label + segmented control 3 options "1,500 / 3,000 / 5,000 words" (selected
    middle).
- "Citation style" segmented control "Numbered [1] / Author-year (Edge 2024)".
- "Optional subtopics" chip input — empty placeholder "+ add subtopic" with example chips
  removable: "Pre-trained models", "Hierarchical KG".
- 1px divider.
- Cost estimator row: secondary "Estimate cost" + result body-sm "≈ 21,500 tokens · ~$0.42 · ~6 min".
- Footer: Secondary "Cancel" + Primary "Run review →" 156×44 brand-500.
```

### S6. Documents — `/lib/:id/docs`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose 1440×900 Documents screen. TopBar shows "◆ RAG-KG ● graphrag-survey / Documents".
SideNav "◇ Documents" active.

Main area padding 32, gap 24:

1) Page header row:
   - Left column: h1 28/33.9 700 "Documents" + caption text-tertiary
     "2,184 docs in graphrag-survey · 62.4k chunks · last sync 8 min ago".
   - Right: Primary button "↑ Upload PDFs" 168×44 brand-500.

2) DropZone (03-U) 1376×120 with the standard message.

3) Documents table (03-V) in a 1376×524 surface, radius 14, bg bg-surface, 1px border-subtle.
   Header row 48h bg bg-subtle (TITLE / YEAR / STATUS / CHUNKS / ENTITIES / INGESTED).
   Render 5 example rows with mixed statuses:
   - Edge et al. "From Local to Global..." (2024) ● Ready 128 / 94 / 3d ago
   - Liu et al. "Hierarchical Community Summaries..." (2025) ● Ready 94 / 71 / 3d ago
   - Wang Asai "Self-RAG..." (2025) ◐ Indexing 62/96 · 70%  / 2m ago
   - Liu Sun "Adaptive Cluster Discovery..." (2025) ◐ Parsing 32% · just now
   - Yang "MultiHop-RAG..." (2024) ⊘ Failed with retry link "↻ Retry with MinerU"
   Each row 1px bottom border-subtle.
   Below table: "… 2,179 more docs" caption text-tertiary centered.

4) Sticky bottom queue summary 1376×40 inside footer: body-sm text-secondary
   "Queue · 14 indexing · 3 parsing · 1 failed" left, and a Cost meter chip right
   "Today $0.36 / $5.00 daily cap".

5) Visualize the FailedErrorPopover (03-AQ) attached above the Yang failed row, anchored at the
   status pill.

Make the table feel data-dense but readable; consistent vertical baselines on numerals.
```

### S7. Cross-Paper Reasoning + Hypothesize — `/lib/:id/reason` & `/lib/:id/hypothesize`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

This screen is a long-scroll 1440×900 visible viewport with two sections stacked vertically.
TopBar "◆ RAG-KG ● graphrag-survey / Reasoning + Hypothesize".
SideNav "◇ Cross-paper reasoning" active (the page hosts both, controlled by inner anchor).

Main padding 32, max-w 720 for prose blocks; 1024 for path canvases.

SECTION 1 — Cross-paper reasoning:

- h1 "Cross-paper reasoning" 28 700.
- Subtitle body 14/22 text-secondary "Multi-hop questions across the corpus, with KG paths +
  evidence timeline + cited conclusion."
- Question card 672×88 radius 14 bg bg-surface 1px border-subtle padding 20: body 14/22 text-primary
  showing the user's question "Did the GraphRAG team's community-summarization approach get
  validated on biomedical drug-repositioning corpora?".
  - Footer row: ghost "Reset" left + Primary "Find paths →" 144×36 brand-500 right.
- PathVisualization 672×320 (03-AC): 3-hop best meta-path with conclusion.
- EvidenceTimeline 672×252 (03-AD).

SECTION 2 — Hypothesize:

- h1 "Hypothesize".
- Subtitle "Provide an entity pair. The system mines KG paths and ranks candidate hypotheses
  by novelty × confidence × verifiability."
- Two entity input fields, side by side, each 320×52 radius 14 bg bg-surface 1px border-default
  padding 12: a "label" line in meta uppercase "Entity A" / "Entity B", then a body 14 600 line
  containing a Concept-style chip "● GraphRAG (Concept)" or "● Drug repositioning (Concept)".
  Each field has a small autocomplete trigger caret.
- Below the inputs: meta "5 candidate hypotheses · sorted by novelty × confidence × verifiability".
- 3 HypothesisCards (03-AE) stacked:
  - Card #1 full 656×180 with the 3 meter bars.
  - Card #2 / #3 compact 656×88.
- Footer row body-sm text-tertiary "+ 2 more · Save shortlist · Export as JSON" with separators.

Empty state note (sticky annotation): "If no path connects the two entities at depth ≤ 3, show
EmptyState 'No path connects the two entities at depth ≤ 3 — try increasing depth, or relaxing
confidence.'"
```

### S8. Eval Dashboard + Settings — `/lib/:id/eval` & `/settings`

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose 1440×900 Eval + Settings combined screen.
TopBar text "◆ RAG-KG ● graphrag-survey / Eval & Settings".
SideNav "◇ Evaluation" active.

Main padding 32, gap 24.

Top header row:
- h1 "Evaluation dashboard"
- Right: LibraryFilter (268×36 select, body-sm 600, leading dot + slug + caret), "Filter: ●
  graphrag-survey ▾".

Subtitle body-sm text-tertiary "smoke (10) · multihop (32) · review (5) · last 30 days".

AlertBanner (03-AI) success "All KPIs within target · last alert 9 days ago." sticky just below
subtitle.

KPI row: 4 KPICards (03-AF) in a row 1376w, gap 16.

Charts row split 64/36:
- LEFT 864×280 TrendBarChart (03-AG).
- RIGHT 496×280 stacked block (Library settings preview card).

Library settings card 496×552 (extends below the trend chart) radius 14 bg bg-surface 1px
border-subtle padding 24:
- Title "Library settings" h3 + meta "graphrag-survey · per-Library overrides shown here".
- Section "MODELS" meta uppercase:
  - "LLM router" label + LLMRouterPicker (03-AM) trigger.
  - "Embedder" label + EmbedderPicker (03-AN) trigger.
- 1px divider.
- Section "BUDGET · per question" — BudgetSettings (03-AO) with 5 numeric fields.
- 1px divider.
- Section "DATA":
  - Secondary button 216×36 "↓ Export Library…"
  - Danger ghost button 216×36 "⊗ Purge Library (irreversible)"
  - Help caption text-tertiary "Drops every Qdrant collection, Neo4j DB, BM25 index, MinIO
    prefix for this Library."

Below the trend chart on the left, FailureCaseTable (03-AH) 864×248.

Tabular numerals throughout. Charts and tables share consistent 14/16.9 body and 11/13.3 meta
labels.
```

---

## §05 Modal & Overlay 提示词（M1–M4）

### M1. LibraryCreateModal

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a centered Modal 600×640 over a rgba(15,15,20,.40) backdrop on a faded LibraryDashboard
behind. radius 20 (radius-xl), bg bg-surface, shadow-lg, padding 32, vertical gap 20.

Header row: title h2 22/26.6 700 "Create a new Library" + close "×" icon top-right.
Subtitle body 14/22 text-secondary 2 lines:
"Each Library is a fully isolated namespace. Documents, KG, embeddings and indices live in
their own physical partitions — no cross-bleed."

Field group 1: "Library ID · slug"
- BaseInput 536×44 prefilled "graphrag-survey", monospace? — keep Inter for consistency.
- Helper body-sm text-tertiary "lowercase, digits, hyphens · 3–30 chars · permanent (can be
  renamed later, slug is fixed)."

Field group 2: "Display name"
- BaseInput 536×44 prefilled "GraphRAG Survey".

Field group 3: "Description"
- BaseTextarea 536×72 prefilled multi-line "GraphRAG, graph-based retrieval, and multi-hop
  reasoning across NLP venues 2023–2025."

Field group 4: "Primary language"
- A 3-button segmented control row, each pill 120×36 radius 10 1px border-default body-sm 600:
  "English" (selected, bg brand-50 text brand-700 1px border brand-500), "中文", "Mixed (zh + en)".

Init help caption text-tertiary:
"Will initialize: Qdrant collection · Neo4j composite DB · Postgres rows · MinIO prefix · BM25
index. ~3s to create."

Footer row: Secondary "Cancel" 100×40 left + Primary "Create Library →" 136×40 right (brand-500).

A subtle warning-50 chip can appear inline if slug is invalid: "Slug already exists" danger-700.

Keyboard hints in footer caption text-tertiary: "↵ submit · Esc close".
```

### M2. DeleteConfirmModal

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a centered danger Modal 600×560 over backdrop. radius 20, bg bg-surface, shadow-lg,
padding 32.

Header cluster (vertically centered):
- 48×48 round icon container bg danger-50 with "⚠" glyph (or Lucide "alert-triangle") in
  danger-700 stroke 1.5.
- Title h2 22/26.6 700 'Purge "graphrag-survey"?' (the slug in mono 22 600 inside double
  quotes).
- Subtitle body 14/22 text-secondary, 2 lines:
  "This action is irreversible. The Library and all its data will be permanently removed."

Impact card 536×144, radius 14, bg danger-50, 1px border-danger-500 at 20%, padding 16:
- Label meta uppercase danger-700 "YOU WILL LOSE".
- List body-sm danger-700 with disc bullets:
  - "2,184 documents (62.4k chunks)"
  - "Knowledge graph (8,491 entities · 31.2k triples)"
  - "Community summaries · embeddings · BM25 indices"
  - "All eval runs · review drafts · session history"

Confirm field: label meta uppercase 'Type "graphrag-survey" to confirm'.
- BaseInput 536×44 prefilled "graphrag-survey" (showing the user typed it correctly →
  Purge button enabled).
- Helper caption text-tertiary "Match must be exact (case-sensitive). Delete button enables when
  the value matches."

Footer row: Secondary "Cancel" 100×40 left + Danger Primary "⊗ Purge Library" 136×40 right
(bg danger-500 text white).

When the input does NOT match: the Purge button is disabled (text-disabled, bg-muted bg).
```

### M3. CommandPaletteOverlay

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a centered Command Palette 720×560 over rgba(15,15,20,.40) backdrop on a faded Chat page.
radius 20, bg bg-surface, shadow-lg.

Input row 720×64, padding 0/20:
- Leading Lucide "search" 18 text-tertiary.
- Big query body-lg 16/22 text-primary showing user's typing "community" with a blinking caret.
- Right kbd hint "esc" inside a 28×20 chip bg bg-subtle text mono-sm 600.
- 1px bottom border-subtle.

Body sections, padding 16/12 horizontal, scrollable up to 432h:

Section 1 — "ENTITIES IN graphrag-survey" meta uppercase 11/13.3 text-tertiary.
- 3 result rows 704×36 radius 8:
  - Active row (first): bg brand-50, text brand-700 600. Layout:
    leading 12 KG type dot, name body-sm 600 "● Community detection",
    meta body-sm text-tertiary "Method · 248 references",
    trailing keyboard hint right-aligned mono-sm "go to KG  ↵".
  - Other 2 rows: bg-surface, hover bg bg-subtle.
    "● Community summarization · Method · 192 refs"
    "● Hierarchical communities (C0–C3) · Concept · 96 refs".

Section 2 — "DOCUMENTS".
- 2 rows 704×36 leading icon "file-text" 14 text-tertiary:
  "📄 Hierarchical Community Summaries for KG QA · Liu et al. 2025"
  "📄 From Local to Global: A Graph RAG Approach · Edge et al. 2024".

Section 3 — "ACTIONS".
- 3 rows 704×36 leading "⌘" kbd chip:
  '⌘R    Generate review on "community summarization" trends'
  '⌘N    Create a new Library'
  '⌘T    Open task page'.

Footer 720×40 bg bg-subtle inset 1px border-subtle, body-sm text-tertiary justified left,
right-aligned kbd hints:
"↑↓ navigate     ↵ open     tab cycle scope     ⌘↩ run     esc close".

The whole palette has subtle 200ms scale-from-0.96 enter animation; outside click closes.
```

### M4. DocumentDetailDrawer

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a right-side Drawer 800×900 over the Documents page (faded behind a 30% black overlay).
radius left 0, right 0, top-right inset radius 20 optional. bg bg-surface, shadow-lg, padding 32,
vertical gap 20.

Header:
- Title h2 22/26.6 700 2-line truncate: "From Local to Global: A Graph RAG Approach to
  Query-Focused Summarization".
- Meta body-sm text-secondary 1 line truncate:
  "Edge, Trinh, Cheng, Bradley, Chao, Mody, Truitt, Larson · Microsoft Research · 2024 ·
  arXiv:2404.16130".
- StatusPill 88×28 "● Ready" success.

Stat row 4 columns, each 80w:
- 128 chunks · 94 entities · 218 triples · 22 pages. Numerals h2 22 700, labels caption
  text-tertiary.

Two-column body (gap 24):

LEFT 336:
- "PDF preview" — 336×408 placeholder card (see 03-X).
- "SECTIONS · 12" meta uppercase. 12 rows with mono caption + section title body-sm.
  "1   Abstract", "2   Introduction", "3   Methods", ...

RIGHT 336:
- "CHUNKS · showing 3 of 128 · filter by section" meta uppercase + a small "filter" link.
- 3 chunk cards (see 03-X): each shows mono "chunk_2871" prefix, position pill "§4.5 · p.4",
  and a 2-line snippet in italic body-sm text-secondary.
- Below: a small "Show all 128 chunks →" body-sm 600 brand-600.

Footer row 800×64 sticky bottom, inset 1px top border-subtle, padding 16:
- Secondary "↻ Re-parse" 152×40 left.
- Primary "Open in Chat / Ask →" 200×40 center-right brand-500.
- Danger ghost "Remove document" 152×40 far right.
```

---

## §06 系统态 / 边界态提示词

> 所有页面都必须配套这些状态。让生成器分别出图，便于装入对应页面替换默认内容。

### 06-A 首次加载 Skeleton

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Render skeleton placeholders for: LibraryCard (320×220), KPICard (336×128), Document row,
ChatMessage. Each uses bg-muted to bg-subtle gradient pulse 1.2s. Display the 4 in a 2×2 grid
with caption captions naming each.
```

### 06-B 流式中断错误

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Inline error appearing right after the streaming caret stops:
- 1 line, body-sm danger-700 weight 600: "Stream interrupted. Retry"
- "Retry" is an underlined link body-sm 600 brand-600.
- A small "info" tooltip on hover explains "Connection lost at token 1,247 — context preserved."
Place it directly under the last partial paragraph in an assistant message.
```

### 06-C 0-hit Evidence Empty

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Inside the EvidencePanel, render a centered EmptyState:
- 40×40 round bg bg-subtle with Lucide "search-x" 20 text-tertiary.
- Title h4 600 "No evidence found".
- Body body-sm text-secondary 2 lines max-w 320: "Try widening the year filter, lowering
  confidence to 0.5, or uploading more papers to this Library."
- Primary outline button "Adjust filters" body-sm 600 brand-600.
```

### 06-D Budget Exceeded Banner

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

A 712×32 inline banner above the Composer in Chat, radius 10, bg danger-50, 1px border-danger-500
at 30%, padding 8/12.
Layout: leading "⚠" icon danger-700 16, body-sm 600 danger-700 "Budget exceeded.", body-sm
danger-700 "Increase or simplify the question.", trailing link "Adjust budget" body-sm 600
brand-600.
```

### 06-E Worker Offline

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Topbar microstate: NotificationBell has an 8 danger-500 dot. To its left, a danger-50 pill 22h
"⊘ Worker offline" with body-sm danger-700; tooltip "Ingest worker offline. Uploads queued."
```

### 06-F Toast 系列

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Render 4 toasts stacked at top-right (24 from edges, 12 vertical gap), each 360×72 (or 64 when
single line):
1) success — "✓ Ingest finished · 124 PDFs added" with sub "drug-target-discovery · KG +812 entities".
2) info    — "ⓘ Review generated · GraphRAG advances 2024–2025" with action link "Open task ↗".
3) warning — "⚠ Stale community detected · rebuild recommended" with action "Rebuild now".
4) danger  — "⊘ Stream interrupted · click to retry" with action "Retry".

Each toast has a 4px left accent bar of its tone, a 20 status icon, title body-sm 600, sub
body-sm text-secondary, close "×".
```

### 06-G Cross-Library Misroute

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Render the LibraryDashboard with a single top-of-page toast slot showing:
"⊘ Library 'foo' does not exist. Redirected to /libraries." auto-dismiss 6s, action "Create
'foo' →" brand-600 link.
```

---

## §07 关键旅程串场提示词（J1 / J2 / J3）

> 用于一次性生成"用户旅程拼图"，每条旅程 1 个长画板，5–6 个小图按时间从左到右排列，方便给团队展示交互轨迹。

### J1. 首次使用 → 第一答案

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

Compose a 2880×900 wide storyboard with 6 thumbnails left-to-right, each 440×900, gap 48,
joined by a thin brand-200 horizontal arrow path with chevrons at each transition:

1) Onboarding (S1 mini).
2) LibraryCreateModal (M1) over a faded onboarding.
3) Empty Chat page (S3) with a top toast "Library ready · upload PDFs to start".
4) Documents page (S6) mid-ingest with 14 indexing rows and the dropzone active.
5) Chat (S3) with a streaming first answer + EvidencePanel showing 3 cards.
6) Click on [1] CitationChip — the panel auto-scrolls to card #1 (highlight bg brand-50).

Above each thumbnail, a meta caption text-tertiary "Step 1 · Onboard" / "Step 6 · Cite".
Below each thumbnail, a body-sm text-secondary single-line description.

Title centered above the board: h2 "J1 · First use → first answer".
```

### J2. 综述生成长任务

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

2880×900 storyboard with 5 thumbnails:
1) Chat (S3) showing the user typing "/review GraphRAG progress 2024-2025".
2) Review config (S5b) prefilled, Estimate cost shown.
3) Review IN-PROGRESS (S5) mid-stream.
4) Mid-run: user clicks "Run in bg ↗" → topbar shows a new red dot on NotificationBell.
5) On completion: toast "✓ Review complete — Open ↗" → drilled into final draft view with
   download button.

Same arrow chevrons; title "J2 · Review long-task with background hand-off".
```

### J3. KG 探索 → 反馈到 Chat

```
You are designing high-fidelity UI for "RAG-KG Copilot" — a private, self-hosted research copilot
that combines dense Retrieval-Augmented Generation with a Knowledge Graph. Audience: PhD students
and small research labs. Aesthetic reference: Linear × Notion × Arc Browser — modern academic SaaS,
calm, dense-but-airy, citation-first, trustworthy.

DESIGN SYSTEM — "Cobalt Lab":

Color (use ONLY these tokens, no other hex):
- Neutrals (warm gray):
  bg-canvas #FAFAF9 (page background, warm white)
  bg-surface #FFFFFF (cards, panels)
  bg-subtle #F4F4F1 (hover / secondary fill)
  bg-muted #EAEAE5 (dividers' fill)
  border-subtle #E4E4E0 (card stroke)
  border-default #D3D3CE (input stroke)
  border-strong #8C8C82 (focus stroke)
  text-primary #1A1A1A
  text-secondary #515151
  text-tertiary #8C8C82
  text-disabled #BDBDB8

- Brand (cobalt indigo, the only "blue"):
  brand-50 #EDF0FF  brand-100 #DCE2FF  brand-200 #B2BCF4
  brand-300 #8D9FFF brand-500 #4F46E4 (PRIMARY action)
  brand-600 #3B30D9 (hover) brand-700 #2A1FAF (active / dark text)

- Semantic (status):
  success: 50 #EBFCF5 / 500 #10B881 / 700 #047856
  warning: 50 #FFFAEB / 500 #F59E0A / 700 #B45208
  danger:  50 #FDF1F1 / 500 #EE4444 / 700 #B91B1B
  info / citation: 50 #EBFDFF / 500 #06B6D3 / 700 #0E7490
  (Citation chips use INFO cyan, never brand indigo — visually distinct from buttons.)

- KG entity types (round dot + same-colored text):
  Concept #4F46E4 (cobalt) · Method #10B881 (emerald) · Dataset #F59E0A (amber)
  Metric #06B6D3 (cyan) · Author #A854F7 (violet) · Venue #EB4799 (pink)

Typography:
- Family: Inter for everything UI (-apple-system / system-ui fallback; PingFang SC for CJK).
- Mono: JetBrains Mono for chunk_ids, DOIs, code, scores.
- Scale (size / line-height, weight):
  display 36/43.6, 700 (hero on Onboarding/Cover)
  h1 28/33.9, 700  · h2 22/26.6, 700  · h3 20/24.2, 600
  h4 18/21.8, 600  · body-lg 16/22, 400
  body 14/16.9, 400  · body-sm 13/15.7, 400
  caption 12/14.5, 400  · meta 11/13.3, 500 (uppercase labels/tags)
  mono 13/20, 400
- Numerals: tabular-nums for stats and KPIs.

Spacing (4px base): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
Grid: 12-column, 24 gutter, max content 1280, side safe 32.

Radius: chip 6 · button/input 10 · card 14 · modal/big-panel 20 · pill 999.

Shadow:
  sm  0 1px 2px rgba(15,15,20,.04)   (card flat)
  md  0 4px 12px rgba(15,15,20,.06)  (raised card / popover)
  lg  0 12px 32px rgba(15,15,20,.10) (modal)
  focus  0 0 0 3px rgba(79,70,229,.20) (a11y focus ring)

Motion:
  hover / focus 120ms ease-out
  modal enter 200ms cubic-bezier(.2,.8,.2,1)
  page transition 240ms ease
  streaming caret 22ms per token, blinking 1.0Hz
  KG node settle 320ms spring

Icons: Lucide line icons, stroke 1.5, sizes 16/20/24.

Global rules:
- Citation-first: every assistant claim has a small numeric pill that links to evidence.
- Library-aware: top bar always shows the active Library (colored dot + slug).
- Progressive disclosure: advanced settings (reranker, budget, schema) live behind ⋯ menus.
- Long-task first-class: review / ingest / reason show explicit progress trees, never spinners.
- Keyboard-native: ⌘K opens command palette; ⌘↩ sends.
- Always include an empty state, a loading skeleton, and an error state.
- A11y: WCAG AA contrast, visible focus ring, ARIA labels on every interactive element.

Render 1× crisp, no shadows on text, no glassmorphism, no neumorphism.
Output: a clean, pixel-precise, production-grade Figma-style frame on a #FAFAF9 canvas.

──────────────────────────────────────────────────────────────────────
TASK — specific component / screen description follows:

2400×900 storyboard with 4 thumbnails:
1) KG Browser (S4) default — canvas filled.
2) Search "GraphRAG" → node centers, edges highlight.
3) EntityDetailDrawer open with neighborhood list.
4) Click "Ask about GraphRAG in Chat →" → Chat page (S3) loaded with prefilled composer text
   "Tell me about GraphRAG" — composer shows the text + active library pill.

Title "J3 · From KG to Chat".
```

---

## 附录 A — Component → Screen 映射速查表

| 组件（§03） | 出现在哪些页面 / Modal |
|---|---|
| TopBar | S2 / S3 / S4 / S5 / S6 / S7 / S8 |
| SideNav | S3 / S4 / S5 / S6 / S7 / S8 |
| LibrarySwitcher | TopBar 内（除 S1） |
| CmdK | TopBar 内（M3 触发） |
| CitationChip | S3 / S5 / S7（answer / draft / conclusion） |
| EvidencePanel | S3 |
| KGCanvas / KGNode / KGEdge | S4 / S7（path 简化版） |
| KGFilterPanel | S4 |
| EntityDetailDrawer | S4 |
| Composer | S3 |
| MessageBubble | S3 |
| ReasoningTrace | S3 |
| DropZone | S6 |
| Document Row | S6 |
| PipelineTree / RunStats | S5 |
| LiveCitationList | S5 |
| ReviewDraftStreaming | S5 |
| PathVisualization | S7 |
| EvidenceTimeline | S7 |
| HypothesisCard | S7 |
| KPICard / TrendBarChart / FailureCaseTable / AlertBanner | S8 |
| LibraryCard / RecentActivityItem / QualityKPIPanel | S2 |
| LLMRouterPicker / EmbedderPicker / BudgetSettings / SchemaEditor | S8（settings 区） |
| FailedErrorPopover | S6（失败行 hover） |
| NotificationBell + Center popover | 全局 |
| I18nSwitcher | 全局 |
| Toast 全套 | 全局 |
| StatusPill | S2 / S6 / S5 / 列表中 |
| Skeleton | 全局加载态 |
| EmptyState | S2/S3/S4/S5/S6/S7（每页必备） |

---

## 附录 B — 复制提示词时的注意事项

1. **每条提示词都先粘贴 §00**，否则模型生成的色系会偏离 Cobalt Lab。
2. **指定输出比例**：主页面 1440×900；Modal 600×640 / 600×560 / 720×560 / 800×900；Storyboard 2400/2880×900。
3. **禁止扩散类美化**：明确写 "no glassmorphism / no neumorphism / no gradient backgrounds / no decorative photography / no AI generic landing-page imagery"。
4. **强调字体一致**：Inter UI + JetBrains Mono for `chunk_id` / `DOI` / `score` / 数值。
5. **强调引用感**：CitationChip 必须是 info-cyan，而不是 brand-indigo，避免和按钮混淆。
6. **强调 Library 上下文**：所有 Library-scoped 页面必须显式出现"● <library-slug>"标识。
7. **强调状态全集**：每个组件都生成 default / hover / active / focus / disabled / loading / error / empty，方便后续手工拼接。
8. **可加 seed 关键词**：附加 "consistent style reference, same canvas tone, 1× crisp, vector-clean lines, no shadows on text"，提升多图风格一致性。

---

**END — 完整提示词手册，与 Figma `A1CKNzyz03sw6iXHvOo2IM` 14 个 Frame 一一对齐。**
