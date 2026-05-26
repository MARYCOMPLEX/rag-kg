# UI 提示词图集 — RAG-KG Copilot

> 自动生成自 `docs/UI_PROMPTS.md`（90 条提示词，已生成 **90** 张）。
> 每张图通过本地 `http://localhost:7000/v1/images/generations` (`model=gpt-image-2`) 接口批量生成。
> 缺失的图说明尚未生成或生成失败 — 重跑 `python scripts/generate_ui_images.py` 即可补齐。

---

## §01 设计系统总览（Tokens 频面）

### §01 设计系统总览（Tokens 频面）

`size: 16:9`  ·  `slug: 01-tokens`

![§01 设计系统总览（Tokens 频面）](ui-images/001-01-tokens.png)

## §02 基础原子组件（Atoms）

### 02-A BaseButton（按钮）

`size: 1:1`  ·  `slug: 02-a-basebutton`

![02-A BaseButton（按钮）](ui-images/002-02-a-basebutton.png)

### 02-B BaseInput（单行输入）

`size: 1:1`  ·  `slug: 02-b-baseinput`

![02-B BaseInput（单行输入）](ui-images/003-02-b-baseinput.png)

### 02-C BaseTextarea（多行输入）

`size: 16:9`  ·  `slug: 02-c-basetextarea`

![02-C BaseTextarea（多行输入）](ui-images/004-02-c-basetextarea.png)

### 02-D BaseSelect（下拉选择）

`size: 1:1`  ·  `slug: 02-d-baseselect`

![02-D BaseSelect（下拉选择）](ui-images/005-02-d-baseselect.png)

### 02-E BaseSlider（滑杆）

`size: 1:1`  ·  `slug: 02-e-baseslider`

![02-E BaseSlider（滑杆）](ui-images/006-02-e-baseslider.png)

### 02-F Checkbox · Radio · Toggle

`size: 1:1`  ·  `slug: 02-f-checkbox-radio-toggle`

![02-F Checkbox · Radio · Toggle](ui-images/007-02-f-checkbox-radio-toggle.png)

### 02-G BaseCard（卡片）

`size: 16:9`  ·  `slug: 02-g-basecard`

![02-G BaseCard（卡片）](ui-images/008-02-g-basecard.png)

### 02-H BaseBadge（徽章）

`size: 1:1`  ·  `slug: 02-h-basebadge`

![02-H BaseBadge（徽章）](ui-images/009-02-h-basebadge.png)

### 02-I BaseChip（带关闭的胶囊）

`size: 1:1`  ·  `slug: 02-i-basechip`

![02-I BaseChip（带关闭的胶囊）](ui-images/010-02-i-basechip.png)

### 02-J BaseTag（用于元数据 inline）

`size: 1:1`  ·  `slug: 02-j-basetag-inline`

![02-J BaseTag（用于元数据 inline）](ui-images/011-02-j-basetag-inline.png)

### 02-K BaseModal（模态）

`size: 1:1`  ·  `slug: 02-k-basemodal`

![02-K BaseModal（模态）](ui-images/012-02-k-basemodal.png)

### 02-L BaseDrawer（抽屉）

`size: 4:3`  ·  `slug: 02-l-basedrawer`

![02-L BaseDrawer（抽屉）](ui-images/013-02-l-basedrawer.png)

### 02-M BaseTooltip · 02-N BasePopover

`size: 1:1`  ·  `slug: 02-m-basetooltip-02-n-basepopover`

![02-M BaseTooltip · 02-N BasePopover](ui-images/014-02-m-basetooltip-02-n-basepopover.png)

### 02-O BaseEmptyState

`size: 1:1`  ·  `slug: 02-o-baseemptystate`

![02-O BaseEmptyState](ui-images/015-02-o-baseemptystate.png)

### 02-P BaseSkeleton

`size: 16:9`  ·  `slug: 02-p-baseskeleton`

![02-P BaseSkeleton](ui-images/016-02-p-baseskeleton.png)

### 02-Q Toast（顶部右）

`size: 1:1`  ·  `slug: 02-q-toast`

![02-Q Toast（顶部右）](ui-images/017-02-q-toast.png)

### 02-R Avatar

`size: 1:1`  ·  `slug: 02-r-avatar`

![02-R Avatar](ui-images/018-02-r-avatar.png)

### 02-S Tabs

`size: 1:1`  ·  `slug: 02-s-tabs`

![02-S Tabs](ui-images/019-02-s-tabs.png)

### 02-T Divider

`size: 1:1`  ·  `slug: 02-t-divider`

![02-T Divider](ui-images/020-02-t-divider.png)

### 02-U Progress Bar & Ring

`size: 1:1`  ·  `slug: 02-u-progress-bar-ring`

![02-U Progress Bar & Ring](ui-images/021-02-u-progress-bar-ring.png)

### 02-V Status Pill（领域级，但归入原子）

`size: 1:1`  ·  `slug: 02-v-status-pill`

![02-V Status Pill（领域级，但归入原子）](ui-images/022-02-v-status-pill.png)

### 02-W IconButton

`size: 1:1`  ·  `slug: 02-w-iconbutton`

![02-W IconButton](ui-images/023-02-w-iconbutton.png)

## §03 领域组件（Domain Components）

### 03-A TopBar（顶栏）

`size: 1:1`  ·  `slug: 03-a-topbar`

![03-A TopBar（顶栏）](ui-images/024-03-a-topbar.png)

### 03-B SideNav（左侧导航）

`size: 9:16`  ·  `slug: 03-b-sidenav`

![03-B SideNav（左侧导航）](ui-images/025-03-b-sidenav.png)

### 03-C SideNav Mini-Stats Card

`size: 1:1`  ·  `slug: 03-c-sidenav-mini-stats-card`

![03-C SideNav Mini-Stats Card](ui-images/026-03-c-sidenav-mini-stats-card.png)

### 03-D LibrarySwitcher

`size: 3:4`  ·  `slug: 03-d-libraryswitcher`

![03-D LibrarySwitcher](ui-images/027-03-d-libraryswitcher.png)

### 03-E Breadcrumb

`size: 1:1`  ·  `slug: 03-e-breadcrumb`

![03-E Breadcrumb](ui-images/028-03-e-breadcrumb.png)

### 03-F CmdK Search Trigger

`size: 1:1`  ·  `slug: 03-f-cmdk-search-trigger`

![03-F CmdK Search Trigger](ui-images/029-03-f-cmdk-search-trigger.png)

### 03-G NotificationBell

`size: 1:1`  ·  `slug: 03-g-notificationbell`

![03-G NotificationBell](ui-images/030-03-g-notificationbell.png)

### 03-H I18nSwitcher

`size: 1:1`  ·  `slug: 03-h-i18nswitcher`

![03-H I18nSwitcher](ui-images/031-03-h-i18nswitcher.png)

### 03-I CitationChip（★ 标志性组件）

`size: 16:9`  ·  `slug: 03-i-citationchip`

![03-I CitationChip（★ 标志性组件）](ui-images/032-03-i-citationchip.png)

### 03-J EvidenceCard

`size: 16:9`  ·  `slug: 03-j-evidencecard`

![03-J EvidenceCard](ui-images/033-03-j-evidencecard.png)

### 03-K EvidencePanel

`size: 1:1`  ·  `slug: 03-k-evidencepanel`

![03-K EvidencePanel](ui-images/034-03-k-evidencepanel.png)

### 03-L MessageBubble — User vs Assistant

`size: 1:1`  ·  `slug: 03-l-messagebubble-user-vs-assistant`

![03-L MessageBubble — User vs Assistant](ui-images/035-03-l-messagebubble-user-vs-assistant.png)

### 03-M ReasoningTrace Toggle

`size: 1:1`  ·  `slug: 03-m-reasoningtrace-toggle`

![03-M ReasoningTrace Toggle](ui-images/036-03-m-reasoningtrace-toggle.png)

### 03-N Composer（聊天输入区，★）

`size: 4:3`  ·  `slug: 03-n-composer`

![03-N Composer（聊天输入区，★）](ui-images/037-03-n-composer.png)

### 03-O SessionList Item

`size: 1:1`  ·  `slug: 03-o-sessionlist-item`

![03-O SessionList Item](ui-images/038-03-o-sessionlist-item.png)

### 03-P KG Canvas

`size: 1:1`  ·  `slug: 03-p-kg-canvas`

![03-P KG Canvas](ui-images/039-03-p-kg-canvas.png)

### 03-Q KG Node

`size: 1:1`  ·  `slug: 03-q-kg-node`

![03-Q KG Node](ui-images/040-03-q-kg-node.png)

### 03-R KG Edge

`size: 1:1`  ·  `slug: 03-r-kg-edge`

![03-R KG Edge](ui-images/041-03-r-kg-edge.png)

### 03-S KG Filter Panel

`size: 9:16`  ·  `slug: 03-s-kg-filter-panel`

![03-S KG Filter Panel](ui-images/042-03-s-kg-filter-panel.png)

### 03-T Entity Detail Drawer (in KG view)

`size: 4:3`  ·  `slug: 03-t-entity-detail-drawer-in-kg-view`

![03-T Entity Detail Drawer (in KG view)](ui-images/043-03-t-entity-detail-drawer-in-kg-view.png)

### 03-U DropZone

`size: 1:1`  ·  `slug: 03-u-dropzone`

![03-U DropZone](ui-images/044-03-u-dropzone.png)

### 03-V Document Row (in Documents table)

`size: 1:1`  ·  `slug: 03-v-document-row-in-documents-table`

![03-V Document Row (in Documents table)](ui-images/045-03-v-document-row-in-documents-table.png)

### 03-W Ingest Progress (per-doc)

`size: 1:1`  ·  `slug: 03-w-ingest-progress-per-doc`

![03-W Ingest Progress (per-doc)](ui-images/046-03-w-ingest-progress-per-doc.png)

### 03-X DocumentDetailDrawer Sections

`size: 1:1`  ·  `slug: 03-x-documentdetaildrawer-sections`

![03-X DocumentDetailDrawer Sections](ui-images/047-03-x-documentdetaildrawer-sections.png)

### 03-Y Pipeline Tree (TaskProgress)

`size: 1:1`  ·  `slug: 03-y-pipeline-tree-taskprogress`

![03-Y Pipeline Tree (TaskProgress)](ui-images/048-03-y-pipeline-tree-taskprogress.png)

### 03-Z Run Stats Sidebar (for long tasks)

`size: 9:16`  ·  `slug: 03-z-run-stats-sidebar-for-long-tasks`

![03-Z Run Stats Sidebar (for long tasks)](ui-images/049-03-z-run-stats-sidebar-for-long-tasks.png)

### 03-AA Live Citation List

`size: 9:16`  ·  `slug: 03-aa-live-citation-list`

![03-AA Live Citation List](ui-images/050-03-aa-live-citation-list.png)

### 03-AB Review Draft Streaming View

`size: 1:1`  ·  `slug: 03-ab-review-draft-streaming-view`

![03-AB Review Draft Streaming View](ui-images/051-03-ab-review-draft-streaming-view.png)

### 03-AC Path Visualization (Reasoning)

`size: 16:9`  ·  `slug: 03-ac-path-visualization-reasoning`

![03-AC Path Visualization (Reasoning)](ui-images/052-03-ac-path-visualization-reasoning.png)

### 03-AD Evidence Timeline

`size: 16:9`  ·  `slug: 03-ad-evidence-timeline`

![03-AD Evidence Timeline](ui-images/053-03-ad-evidence-timeline.png)

### 03-AE Hypothesis Card

`size: 16:9`  ·  `slug: 03-ae-hypothesis-card`

![03-AE Hypothesis Card](ui-images/054-03-ae-hypothesis-card.png)

### 03-AF KPI Card

`size: 16:9`  ·  `slug: 03-af-kpi-card`

![03-AF KPI Card](ui-images/055-03-af-kpi-card.png)

### 03-AG Trend Bar Chart

`size: 16:9`  ·  `slug: 03-ag-trend-bar-chart`

![03-AG Trend Bar Chart](ui-images/056-03-ag-trend-bar-chart.png)

### 03-AH Failure Case Table

`size: 16:9`  ·  `slug: 03-ah-failure-case-table`

![03-AH Failure Case Table](ui-images/057-03-ah-failure-case-table.png)

### 03-AI Alert Banner

`size: 1:1`  ·  `slug: 03-ai-alert-banner`

![03-AI Alert Banner](ui-images/058-03-ai-alert-banner.png)

### 03-AJ Library Card

`size: 4:3`  ·  `slug: 03-aj-library-card`

![03-AJ Library Card](ui-images/059-03-aj-library-card.png)

### 03-AK Recent Activity Item

`size: 1:1`  ·  `slug: 03-ak-recent-activity-item`

![03-AK Recent Activity Item](ui-images/060-03-ak-recent-activity-item.png)

### 03-AL Quality KPI Panel

`size: 1:1`  ·  `slug: 03-al-quality-kpi-panel`

![03-AL Quality KPI Panel](ui-images/061-03-al-quality-kpi-panel.png)

### 03-AM LLM Router Picker

`size: 4:3`  ·  `slug: 03-am-llm-router-picker`

![03-AM LLM Router Picker](ui-images/062-03-am-llm-router-picker.png)

### 03-AN Embedder Picker

`size: 1:1`  ·  `slug: 03-an-embedder-picker`

![03-AN Embedder Picker](ui-images/063-03-an-embedder-picker.png)

### 03-AO Budget Settings Form

`size: 1:1`  ·  `slug: 03-ao-budget-settings-form`

![03-AO Budget Settings Form](ui-images/064-03-ao-budget-settings-form.png)

### 03-AP Schema Editor

`size: 16:9`  ·  `slug: 03-ap-schema-editor`

![03-AP Schema Editor](ui-images/065-03-ap-schema-editor.png)

### 03-AQ Failed Error Popover

`size: 16:9`  ·  `slug: 03-aq-failed-error-popover`

![03-AQ Failed Error Popover](ui-images/066-03-aq-failed-error-popover.png)

### 03-AR Cost Meter

`size: 1:1`  ·  `slug: 03-ar-cost-meter`

![03-AR Cost Meter](ui-images/067-03-ar-cost-meter.png)

## §04 主页面提示词（Screens S1–S8）

### S1. Onboarding — `/onboarding`

`size: 16:9`  ·  `slug: s1-onboarding-onboarding`

![S1. Onboarding — `/onboarding`](ui-images/068-s1-onboarding-onboarding.png)

### S2. Library Dashboard — `/libraries`

`size: 16:9`  ·  `slug: s2-library-dashboard-libraries`

![S2. Library Dashboard — `/libraries`](ui-images/069-s2-library-dashboard-libraries.png)

### S3. ★ Chat / QA — `/lib/:id/chat`

`size: 16:9`  ·  `slug: s3-chat-qa-lib-idchat`

![S3. ★ Chat / QA — `/lib/:id/chat`](ui-images/070-s3-chat-qa-lib-idchat.png)

### S4. KG Browser — `/lib/:id/kg`

`size: 16:9`  ·  `slug: s4-kg-browser-lib-idkg`

![S4. KG Browser — `/lib/:id/kg`](ui-images/071-s4-kg-browser-lib-idkg.png)

### S5. Review Generation (in progress) — `/lib/:id/review/:taskId`

`size: 16:9`  ·  `slug: s5-review-generation-in-progress-lib-idreview-taskid`

![S5. Review Generation (in progress) — `/lib/:id/review/:taskId`](ui-images/072-s5-review-generation-in-progress-lib-idreview-taskid.png)

### S5b. Review Configuration (pre-run) — `/lib/:id/review`

`size: 16:9`  ·  `slug: s5b-review-configuration-pre-run-lib-idreview`

![S5b. Review Configuration (pre-run) — `/lib/:id/review`](ui-images/073-s5b-review-configuration-pre-run-lib-idreview.png)

### S6. Documents — `/lib/:id/docs`

`size: 16:9`  ·  `slug: s6-documents-lib-iddocs`

![S6. Documents — `/lib/:id/docs`](ui-images/074-s6-documents-lib-iddocs.png)

### S7. Cross-Paper Reasoning + Hypothesize — `/lib/:id/reason` & `/lib/:id/hypothesize`

`size: 16:9`  ·  `slug: s7-cross-paper-reasoning-hypothesize-lib-idreason-lib-idhypothesize`

![S7. Cross-Paper Reasoning + Hypothesize — `/lib/:id/reason` & `/lib/:id/hypothesize`](ui-images/075-s7-cross-paper-reasoning-hypothesize-lib-idreason-lib-idhypothesize.png)

### S8. Eval Dashboard + Settings — `/lib/:id/eval` & `/settings`

`size: 16:9`  ·  `slug: s8-eval-dashboard-settings-lib-ideval-settings`

![S8. Eval Dashboard + Settings — `/lib/:id/eval` & `/settings`](ui-images/076-s8-eval-dashboard-settings-lib-ideval-settings.png)

## §05 Modal & Overlay 提示词（M1–M4）

### M1. LibraryCreateModal

`size: 1:1`  ·  `slug: m1-librarycreatemodal`

![M1. LibraryCreateModal](ui-images/077-m1-librarycreatemodal.png)

### M2. DeleteConfirmModal

`size: 1:1`  ·  `slug: m2-deleteconfirmmodal`

![M2. DeleteConfirmModal](ui-images/078-m2-deleteconfirmmodal.png)

### M3. CommandPaletteOverlay

`size: 4:3`  ·  `slug: m3-commandpaletteoverlay`

![M3. CommandPaletteOverlay](ui-images/079-m3-commandpaletteoverlay.png)

### M4. DocumentDetailDrawer

`size: 1:1`  ·  `slug: m4-documentdetaildrawer`

![M4. DocumentDetailDrawer](ui-images/080-m4-documentdetaildrawer.png)

## §06 系统态 / 边界态提示词

### 06-A 首次加载 Skeleton

`size: 4:3`  ·  `slug: 06-a-skeleton`

![06-A 首次加载 Skeleton](ui-images/081-06-a-skeleton.png)

### 06-B 流式中断错误

`size: 1:1`  ·  `slug: 06-b`

![06-B 流式中断错误](ui-images/082-06-b.png)

### 06-C 0-hit Evidence Empty

`size: 1:1`  ·  `slug: 06-c-0-hit-evidence-empty`

![06-C 0-hit Evidence Empty](ui-images/083-06-c-0-hit-evidence-empty.png)

### 06-D Budget Exceeded Banner

`size: 1:1`  ·  `slug: 06-d-budget-exceeded-banner`

![06-D Budget Exceeded Banner](ui-images/084-06-d-budget-exceeded-banner.png)

### 06-E Worker Offline

`size: 1:1`  ·  `slug: 06-e-worker-offline`

![06-E Worker Offline](ui-images/085-06-e-worker-offline.png)

### 06-F Toast 系列

`size: 1:1`  ·  `slug: 06-f-toast`

![06-F Toast 系列](ui-images/086-06-f-toast.png)

### 06-G Cross-Library Misroute

`size: 1:1`  ·  `slug: 06-g-cross-library-misroute`

![06-G Cross-Library Misroute](ui-images/087-06-g-cross-library-misroute.png)

## §07 关键旅程串场提示词（J1 / J2 / J3）

### J1. 首次使用 → 第一答案

`size: 16:9`  ·  `slug: j1`

![J1. 首次使用 → 第一答案](ui-images/088-j1.png)

### J2. 综述生成长任务

`size: 16:9`  ·  `slug: j2`

![J2. 综述生成长任务](ui-images/089-j2.png)

### J3. KG 探索 → 反馈到 Chat

`size: 16:9`  ·  `slug: j3-kg-chat`

![J3. KG 探索 → 反馈到 Chat](ui-images/090-j3-kg-chat.png)
