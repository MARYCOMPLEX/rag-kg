# RAG-KG Copilot Frontend Design Spec

**Source**: Figma file `A1CKNzyz03sw6iXHvOo2IM`
**Generated**: extracted via Figma REST API (figd token)
**Authority**: this doc supersedes ad-hoc UI implementations.

---

## 1. Design Tokens (extracted across all 14 frames)

### 1.1 Color palette (sorted by usage)

| Hex | Usage |
|---|---|
| `#8C8C82` | 141 |
| `#1A1A1A` | 98 |
| `#FFFFFF` | 90 |
| `#515151` | 86 |
| `#4F46E4` | 48 |
| `#E4E4E0` | 39 |
| `#F4F4F1` | 23 |
| `#10B881` | 22 |
| `#EAEAE5` | 20 |
| `#D3D3CE` | 16 |
| `#8D9FFF` | 15 |
| `#F9F9F8` | 10 |
| `#2A1FAF` | 10 |
| `#047856` | 10 |
| `#EDF0FF` | 9 |
| `#EBFCF5` | 9 |
| `#B91B1B` | 8 |
| `#F59E0A` | 7 |
| `#EE4444` | 7 |
| `#EBFDFF` | 7 |
| `#0E7490` | 7 |
| `#B45208` | 6 |
| `#06B6D3` | 4 |
| `#FFFAEB` | 4 |
| `#A854F7` | 3 |
| `#FDF1F1` | 3 |
| `#DBE2FF` | 2 |
| `#B2BCF4` | 1 |
| `#DCE2FF` | 1 |
| `#EB4799` | 1 |
| `#8A8A85` | 1 |
| `#F7ECFF` | 1 |
| `#702BB0` | 1 |
| `#FCE8F2` | 1 |
| `#AF1358` | 1 |
| `#FAFAF9` | 1 |

### 1.2 Typography (Inter / system)

| Family | Style | Size / LineHeight | Usage |
|---|---|---|---|
| Inter | Medium | 11/13.3 | 38 |
| Inter | Bold | 11/13.3 | 30 |
| Inter | Semi Bold | 12/14.5 | 30 |
| Inter | Regular | 12/14.5 | 27 |
| Inter | Bold | 22/26.6 | 27 |
| Inter | Medium | 14/16.9 | 25 |
| Inter | Regular | 11/13.3 | 23 |
| Inter | Medium | 12/14.5 | 23 |
| Inter | Medium | 13/15.7 | 23 |
| Inter | Bold | 12/14.5 | 21 |
| Inter | Semi Bold | 11/13.3 | 19 |
| Inter | Semi Bold | 13/15.7 | 19 |
| Inter | Regular | 13/15.7 | 18 |
| Inter | Semi Bold | 14/16.9 | 17 |
| Inter | Regular | 14/16.9 | 16 |
| Inter | Medium | 10/12.1 | 7 |
| Inter | Bold | 10/12.1 | 6 |
| Inter | Regular | 15/18.2 | 6 |
| Inter | Bold | 14/16.9 | 5 |
| Inter | Bold | 18/21.8 | 5 |
| Inter | Semi Bold | 20/24.2 | 5 |
| Inter | Semi Bold | 18/21.8 | 4 |
| Inter | Bold | 36/43.6 | 4 |
| Inter | Semi Bold | 10/12.1 | 3 |
| Inter | Bold | 28/33.9 | 3 |
| Inter | Semi Bold | 15/18.2 | 2 |
| Inter | Bold | 15/18.2 | 2 |
| Inter | Bold | 16/19.4 | 2 |
| Inter | Semi Bold | 17/20.6 | 2 |
| Inter | Regular | 18/21.8 | 2 |
| Inter | Bold | 13/15.7 | 1 |
| Inter | Medium | 15/18.2 | 1 |
| Inter | Regular | 16/19.4 | 1 |
| Inter | Medium | 17/20.6 | 1 |
| Inter | Medium | 18/21.8 | 1 |
| Inter | Regular | 22/26.6 | 1 |
| Inter | Semi Bold | 22/26.6 | 1 |
| Inter | Bold | 26/31.5 | 1 |
| Inter | Bold | 32/38.7 | 1 |
| Inter | Bold | 40/48.4 | 1 |
| Inter | Light | 40/48.4 | 1 |
| Inter | Bold | 52/62.9 | 1 |
| Inter | Bold | 72/87.1 | 1 |

### 1.3 Border radius values

- `999.0` (54×)
- `10.0` (45×)
- `14.0` (28×)
- `6.0` (13×)
- `8.0` (6×)
- `12.0` (6×)
- `20.0` (3×)
- `16.0` (1×)

### 1.4 Auto-layout item spacing values



### 1.5 Padding (top/right/bottom/left)



### 1.6 Shadow effects


---

## 2. Frame inventory & hierarchies

### Cover (`5:2` — 2960×400)

```
- `[Cover] RAG-KG Copilot — Design System & Screens` (FRAME 2960×400)
  - `cover-title` (TEXT: "RAG-KG Copilot")
  - `cover-subtitle` (TEXT: "Your private RAG + Knowledge-Graph copilot for ser...")
  - `cover-version-chip` (RECTANGLE 280×36)
  - `cover-version-text` (TEXT: "v0.1 · UI Spec aligned w/ M7")
  - `cover-tagline` (TEXT: "8 Screens · 1 Design System · Citation-first")
  - `cover-meta` (TEXT: ""Cobalt Lab" · Inter / JetBrains Mono · Naive UI +...")
```

### Tokens (`6:9` — 2960×1320)

```
- `[Tokens] Design System` (FRAME 2960×1320)
  - `tokens-title` (TEXT: "Design Tokens — Cobalt Lab")
  - `tokens-subtitle` (TEXT: "Color · Typography · Spacing & Radius · Shadow · K...")
  - `label-neutrals` (TEXT: "NEUTRALS  ·  warm gray")
  - `neutral/bg-canvas` (RECTANGLE 120×100)
  - `neutral/bg-surface` (RECTANGLE 120×100)
  - `neutral/bg-subtle` (RECTANGLE 120×100)
  - `neutral/border` (RECTANGLE 120×100)
  - `neutral/text-secondary` (RECTANGLE 120×100)
  - `neutral/text-primary` (RECTANGLE 120×100)
  - `label-bg-canvas` (TEXT: "bg-canvas
#FAFAF9")
  - `label-bg-surface` (TEXT: "bg-surface
#FFFFFF")
  - `label-bg-subtle` (TEXT: "bg-subtle
#F4F4F2")
  - `label-border` (TEXT: "border
#D4D4CE")
  - `label-text-secondary` (TEXT: "text-secondary
#525252")
  - `label-text-primary` (TEXT: "text-primary
#1A1A1A")
  - `label-brand` (TEXT: "BRAND  ·  cobalt indigo")
  - `brand/50` (RECTANGLE 120×100)
  - `brand/100` (RECTANGLE 120×100)
  - `brand/300` (RECTANGLE 120×100)
  - `brand/500` (RECTANGLE 120×100)
  - `brand/700` (RECTANGLE 120×100)
  - `label-semantic` (TEXT: "SEMANTIC  ·  status")
  - `semantic/success-500` (RECTANGLE 120×100)
  - `semantic/warning-500` (RECTANGLE 120×100)
  - `semantic/danger-500` (RECTANGLE 120×100)
  - `semantic/info-500` (RECTANGLE 120×100)
  - `label-kg` (TEXT: "KG ENTITY  ·  6 types")
  - `kg/concept` (RECTANGLE 120×100)
  - `kg/method` (RECTANGLE 120×100)
  - `kg/dataset` (RECTANGLE 120×100)
  - `kg/metric` (RECTANGLE 120×100)
  - `kg/author` (RECTANGLE 120×100)
  - `kg/venue` (RECTANGLE 120×100)
```

### S1 Onboarding (`6:43` — 1440×900)

```
- `[S1] Onboarding — Desktop 1440` (FRAME 1440×900)
  - `s1-hero-title` (TEXT: "Your private RAG-KG Copilot.")
  - `s1-hero-subtitle` (TEXT: "Drop your PDFs into a Library. Ask questions. Get ...")
  - `s1-step-1` (FRAME 240×200)
    - `step-1-num` (TEXT: "01")
    - `step-1-title` (TEXT: "Create a Library")
    - `step-1-desc` (TEXT: "Each research direction
lives in its own isolated
...")
  - `s1-step-2` (FRAME 240×200)
    - `step-2-num` (TEXT: "02")
    - `step-2-title` (TEXT: "Drop your PDFs")
    - `step-2-desc` (TEXT: "Parse, embed, and build
a knowledge graph
automati...")
  - `s1-step-3` (FRAME 240×200)
    - `step-3-num` (TEXT: "03")
    - `step-3-title` (TEXT: "Ask with citations")
    - `step-3-desc` (TEXT: "Every answer comes with
verifiable evidence chips
...")
  - `s1-cta-primary` (RECTANGLE 280×52)
  - `s1-cta-primary-text` (TEXT: "Create your first Library  →")
  - `s1-cta-secondary` (TEXT: "or  See a demo Library")
  - `s1-trust-line` (TEXT: "No account needed · Self-hosted · Your data stays ...")
  - `s1-logo-mark` (RECTANGLE 40×40)
  - `s1-logo-text` (TEXT: "RAG-KG Copilot")
```

### S2 Library Dashboard (`7:64` — 1440×900)

```
- `[S2] Library Dashboard — Desktop 1440` (FRAME 1440×900)
  - `s2-topbar` (RECTANGLE 1440×56)
  - `s2-logo-mark` (RECTANGLE 24×24)
  - `s2-logo-text` (TEXT: "RAG-KG")
  - `s2-library-switcher` (RECTANGLE 280×32)
  - `s2-lib-dot` (RECTANGLE 12×12)
  - `s2-lib-name` (TEXT: "graphrag-survey")
  - `s2-lib-caret` (TEXT: "▾")
  - `s2-cmdk` (RECTANGLE 120×32)
  - `s2-cmdk-text` (TEXT: "Search...    ⌘K")
  - `s2-avatar` (RECTANGLE 32×32)
  - `s2-avatar-text` (TEXT: "T")
  - `s2-page-title` (TEXT: "Your Libraries")
  - `s2-page-meta` (TEXT: "3 active libraries · 4,872 documents · 142,108 chu...")
  - `s2-card-1` (FRAME 320×220)
    - `card-1-title` (TEXT: "graphrag-survey")
    - `card-1-status` (RECTANGLE 76×22)
    - `card-1-status-text` (TEXT: "● Healthy")
    - `card-1-desc` (TEXT: "GraphRAG, graph-based retrieval,
and multi-hop rea...")
    - `card-1-stat-docs` (TEXT: "2,184")
    - `card-1-stat-docs-label` (TEXT: "docs")
    - `card-1-stat-chunks` (TEXT: "62.4k")
    - `card-1-stat-chunks-label` (TEXT: "chunks")
    - `card-1-stat-entities` (TEXT: "8,491")
    - `card-1-stat-entities-label` (TEXT: "entities")
    - `card-1-stat-triples` (TEXT: "31.2k")
    - `card-1-stat-triples-label` (TEXT: "triples")
  - `s2-card-1` (FRAME 320×220)
    - `card-1-title` (TEXT: "drug-target-discovery")
    - `card-1-status` (RECTANGLE 76×22)
    - `card-1-status-text` (TEXT: "● Healthy")
    - `card-1-desc` (TEXT: "Drug repositioning, target ID, and
small-molecule ...")
    - `card-1-stat-docs` (TEXT: "1,907")
    - `card-1-stat-docs-label` (TEXT: "docs")
    - `card-1-stat-chunks` (TEXT: "54.8k")
    - `card-1-stat-chunks-label` (TEXT: "chunks")
    - `card-1-stat-entities` (TEXT: "11.2k")
    - `card-1-stat-entities-label` (TEXT: "entities")
    - `card-1-stat-triples` (TEXT: "42.7k")
    - `card-1-stat-triples-label` (TEXT: "triples")
  - `s2-card-1` (FRAME 320×220)
    - `card-1-title` (TEXT: "neuro-causal-inference")
    - `card-1-status` (RECTANGLE 76×22)
    - `card-1-status-text` (TEXT: "● Indexing")
    - `card-1-desc` (TEXT: "Causal inference in neural circuits
and counterfac...")
    - `card-1-stat-docs` (TEXT: "781")
    - `card-1-stat-docs-label` (TEXT: "docs")
    - `card-1-stat-chunks` (TEXT: "24.9k")
    - `card-1-stat-chunks-label` (TEXT: "chunks")
    - `card-1-stat-entities` (TEXT: "3,204")
    - `card-1-stat-entities-label` (TEXT: "entities")
    - `card-1-stat-triples` (TEXT: "9,186")
    - `card-1-stat-triples-label` (TEXT: "triples")
  - `s2-card-new` (FRAME 320×220)
    - `card-new-icon-bg` (RECTANGLE 64×64)
    - `card-new-plus` (TEXT: "+")
    - `card-new-title` (TEXT: "New Library")
    - `card-new-desc` (TEXT: "Start a new research direction")
  - `s2-section-activity` (TEXT: "Recent activity")
  - `s2-activity-list` (FRAME 896×320)
    - `activity-1-title` (TEXT: "Review generation completed: "GraphRAG advances 20...")
    - `activity-1-meta` (TEXT: "graphrag-survey · 3,142 words · 47 citations")
    - `activity-1-time` (TEXT: "14m ago")
    - `activity-divider-1` (RECTANGLE 896×1)
    - `activity-2-title` (TEXT: "Ingest finished: 124 papers added to drug-target-d...")
    - `activity-2-meta` (TEXT: "drug-target-discovery · 4,108 new chunks · KG +812...")
    - `activity-2-time` (TEXT: "2h ago")
    - `activity-divider-2` (RECTANGLE 896×1)
    - `activity-3-title` (TEXT: "Community rebuild · 47 communities (Leiden depth 3...")
    - `activity-3-meta` (TEXT: "graphrag-survey · ran for 92s · summary cost $0.34")
    - `activity-3-time` (TEXT: "yesterday")
  - `s2-kpi-title` (TEXT: "Quality at a glance")
  - `s2-kpi-panel` (FRAME 384×320)
    - `kpi-var-label` (TEXT: "Valid Answer Rate (VAR)")
    - `kpi-var-value` (TEXT: "76.4%")
    - `kpi-var-delta` (TEXT: "↑ 2.1pp this week")
    - `kpi-divider-1` (RECTANGLE 336×1)
    - `kpi-cit-label` (TEXT: "Citation F1")
    - `kpi-cit-value` (TEXT: "0.872")
    - `kpi-p95-label` (TEXT: "P95 latency")
    - `kpi-p95-value` (TEXT: "14.2s")
    - `kpi-divider-2` (RECTANGLE 336×1)
    - `kpi-cost-label` (TEXT: "$ / question (avg)")
    - `kpi-cost-value` (TEXT: "$0.084")
    - `kpi-recall-label` (TEXT: "Recall@10")
    - `kpi-recall-value` (TEXT: "0.74")
    - `kpi-targets` (TEXT: "Targets · VAR ≥ 75% · Citation F1 ≥ 0.85 · P95 ≤ 2...")
  - `s2-i18n-toggle` (FRAME 36×32)
    - `s2-i18n-text` (TEXT: "EN ▾")
  - `s2-legend-label` (TEXT: "Library status legend:")
  - `s2-legend-healthy` (FRAME 76×22)
    - `s2-legend-healthy-text` (TEXT: "● Healthy")
  - `s2-legend-indexing` (FRAME 76×22)
    - `s2-legend-indexing-text` (TEXT: "◐ Indexing")
  - `s2-legend-stale` (FRAME 132×22)
    - `s2-legend-stale-text` (TEXT: "⚠ Stale community")
```

### S3 Chat / QA (★ flagship) (`15:151` — 1440×900)

```
- `[S3] Chat / QA — Desktop 1440 (★ flagship)` (FRAME 1440×900)
  - `s3-topbar` (RECTANGLE 1440×56)
  - `s3-logo-mark` (RECTANGLE 24×24)
  - `s3-logo-text` (TEXT: "RAG-KG")
  - `s3-library-switcher` (RECTANGLE 240×32)
  - `s3-lib-dot` (RECTANGLE 12×12)
  - `s3-lib-name` (TEXT: "graphrag-survey   ▾")
  - `s3-breadcrumb` (TEXT: "/  Chat  /  Session 2026-05-05")
  - `s3-cmdk` (RECTANGLE 120×32)
  - `s3-cmdk-text` (TEXT: "Search...    ⌘K")
  - `s3-notify` (RECTANGLE 32×32)
  - `s3-notify-icon` (TEXT: "🔔")
  - `s3-avatar` (RECTANGLE 32×32)
  - `s3-avatar-text` (TEXT: "T")
  - `s3-sidenav` (RECTANGLE 240×844)
  - `s3-nav-group-1` (TEXT: "WORKSPACE")
  - `s3-nav-active-bg` (RECTANGLE 216×36)
  - `s3-nav-overview` (TEXT: "◇   Overview")
  - `s3-nav-chat` (TEXT: "◆   Chat")
  - `s3-nav-docs` (TEXT: "◇   Documents")
  - `s3-nav-kg` (TEXT: "◇   Knowledge Graph")
  - `s3-nav-group-2` (TEXT: "TASKS")
  - `s3-nav-review` (TEXT: "◇   Review generation")
  - `s3-nav-reason` (TEXT: "◇   Cross-paper reasoning")
  - `s3-nav-hypo` (TEXT: "◇   Hypothesize")
  - `s3-nav-eval` (TEXT: "◇   Evaluation")
  - `s3-nav-mini-stats` (FRAME 216×180)
    - `mini-stats-title` (TEXT: "graphrag-survey")
    - `mini-stats-body` (TEXT: "2,184 docs · 62.4k chunks
8,491 entities · 31.2k t...")
  - `s3-session-meta` (TEXT: "Session · 2026-05-05 · 14:32")
  - `s3-session-title` (TEXT: "How does GraphRAG combine community summarization ...")
  - `s3-session-divider` (RECTANGLE 680×1)
  - `user-avatar` (RECTANGLE 28×28)
  - `user-avatar-text` (TEXT: "T")
  - `user-name` (TEXT: "You")
  - `user-content` (TEXT: "In the GraphRAG paper they talk about "global" and...")
  - `bot-avatar` (RECTANGLE 28×28)
  - `bot-name` (TEXT: "RAG-KG  ·  Claude Haiku 4.5")
  - `bot-para-1` (TEXT: "GraphRAG splits retrieval into two complementary m...")
  - `bot-para-2-pre` (TEXT: "In local mode, the planner expands from the matche...")
  - `cite-1` (RECTANGLE 26×20)
  - `cite-1-text` (TEXT: "1")
  - `bot-para-2-mid` (TEXT: ". In global mode, the system instead reads")
  - `bot-para-2-line2` (TEXT: "community-level summaries (built ahead of time by ...")
  - `bot-para-2-line3` (TEXT: "retrieves the top-K relevant communities, and asks...")
  - `cite-2` (RECTANGLE 26×20)
  - `cite-2-text` (TEXT: "2")
  - `s3-trace-toggle` (TEXT: "▾  Show reasoning trace  ·  6 retrieval steps  ·  ...")
  - `s3-composer` (FRAME 712×112)
    - `composer-placeholder` (TEXT: "Ask anything in this Library...    type "/" for co...")
    - `composer-lib-pill` (RECTANGLE 152×28)
    - `composer-lib-text` (TEXT: "● graphrag-survey")
    - `composer-model` (TEXT: "Claude Haiku 4.5  ▾")
    - `composer-budget` (TEXT: "Budget · 8 steps · 32k tok")
    - `composer-send` (RECTANGLE 72×32)
    - `composer-send-text` (TEXT: "⌘↩  Send")
  - `s3-evidence-panel` (RECTANGLE 440×844)
  - `evidence-title` (TEXT: "Evidence")
  - `evidence-meta` (TEXT: "3 sources cited · click [n] in answer to jump")
  - `evidence-card-1` (FRAME 392×196)
    - `ev1-cite-chip` (RECTANGLE 26×20)
    - `ev1-cite-num` (TEXT: "1")
    - `ev1-title` (TEXT: "From Local to Global: A Graph RAG
Approach to Quer...")
    - `ev1-meta` (TEXT: "Edge et al. · 2024 · Microsoft Research")
    - `ev1-quote` (TEXT: ""...we observe that local search is appropriate
wh...")
    - `ev1-footer` (TEXT: "vector · score 0.91   ·   p. 4 §3.2   ·   chunk_28...")
  - `evidence-card-1` (FRAME 392×196)
    - `ev1-cite-chip` (RECTANGLE 26×20)
    - `ev1-cite-num` (TEXT: "2")
    - `ev1-title` (TEXT: "Hierarchical Community Summaries
for Knowledge Gra...")
    - `ev1-meta` (TEXT: "Liu et al. · 2025 · ACL")
    - `ev1-quote` (TEXT: ""...Leiden communities at depth-3 yield
the most i...")
    - `ev1-footer` (TEXT: "graph + community · score 0.84   ·   community c-1...")
  - `evidence-card-1` (FRAME 392×196)
    - `ev1-cite-chip` (RECTANGLE 26×20)
    - `ev1-cite-num` (TEXT: "3")
    - `ev1-title` (TEXT: "Reciprocal Rank Fusion in
Multi-Stage Retrieval")
    - `ev1-meta` (TEXT: "Cormack et al. · 2009 · SIGIR")
    - `ev1-quote` (TEXT: ""...RRF assigns each candidate a score
of Σ 1/(k+r...")
    - `ev1-footer` (TEXT: "bm25 + vector RRF · score 0.78   ·   chunk_8419")
  - `s3-sessions-label` (TEXT: "RECENT SESSIONS")
  - `s3-sessions-list` (TEXT: "→  GraphRAG local vs global       now
   How does ...")
  - `s3-session-active-rail` (RECTANGLE 3×28)
  - `s3-empty-state-note` (TEXT: "Empty state: 0-hit retrieval shows "No evidence fo...")
```

### S4 KG Browser (`15:231` — 1440×900)

```
- `[S4] KG Browser — Desktop 1440` (FRAME 1440×900)
  - `s4-topbar` (RECTANGLE 1440×56)
  - `s4-topbar-text` (TEXT: "◆ RAG-KG    ●  graphrag-survey  /  Knowledge Graph")
  - `s4-filter-panel` (RECTANGLE 280×844)
  - `s4-filter-title` (TEXT: "Filters")
  - `s4-search` (RECTANGLE 232×36)
  - `s4-search-text` (TEXT: "🔍  Search entity...")
  - `s4-types-label` (TEXT: "ENTITY TYPES")
  - `s4-type-concept` (RECTANGLE 68×26)
  - `s4-type-concept-text` (TEXT: "● Concept")
  - `s4-type-method` (FRAME 68×26)
    - `s4-type-method-text` (TEXT: "● Method")
  - `s4-type-dataset` (FRAME 68×26)
    - `s4-type-dataset-text` (TEXT: "● Dataset")
  - `s4-type-metric` (FRAME 68×26)
    - `s4-type-metric-text` (TEXT: "● Metric")
  - `s4-type-author` (FRAME 68×26)
    - `s4-type-author-text` (TEXT: "● Author")
  - `s4-type-venue` (FRAME 68×26)
    - `s4-type-venue-text` (TEXT: "● Venue")
  - `s4-depth-label` (TEXT: "DEPTH  ·  k-hop neighborhood")
  - `s4-depth-track` (RECTANGLE 232×4)
  - `s4-depth-fill` (RECTANGLE 120×4)
  - `s4-depth-thumb` (RECTANGLE 16×16)
  - `s4-depth-marks` (TEXT: "1-hop      2-hop      3-hop")
  - `s4-conf-label` (TEXT: "CONFIDENCE  ≥ 0.65")
  - `s4-conf-track` (RECTANGLE 232×4)
  - `s4-conf-fill` (RECTANGLE 152×4)
  - `s4-viewstats-label` (TEXT: "VIEW STATS")
  - `s4-viewstats-text` (TEXT: "8,491 entities (top 50 shown)
31,219 triples · con...")
  - `s4-canvas` (FRAME 800×844)
    - `s4-canvas-label` (TEXT: "Knowledge graph · graphrag-survey")
    - `node-graphrag` (FRAME 96×96)
      - `node-graphrag-label` (TEXT: "GraphRAG")
    - `node-leiden` (FRAME 128×52)
      - `node-leiden-label` (TEXT: "Leiden algorithm")
    - `node-community` (FRAME 152×52)
      - `node-community-label` (TEXT: "Community detection")
    - `node-vector` (FRAME 128×52)
      - `node-vector-label` (TEXT: "Vector retrieval")
    - `node-global` (FRAME 128×52)
      - `node-global-label` (TEXT: "Global search")
    - `node-local` (FRAME 128×52)
      - `node-local-label` (TEXT: "Local search")
    - `node-msdataset` (FRAME 128×52)
      - `node-msdataset-label` (TEXT: "MultiHop-RAG dataset")
    - `node-recall` (FRAME 112×44)
      - `node-recall-label` (TEXT: "Recall@10")
    - `node-edge` (FRAME 112×44)
      - `node-edge-label` (TEXT: "D. Edge et al.")
    - `node-rrf` (FRAME 112×44)
      - `node-rrf-label` (TEXT: "RRF")
  - `s4-detail-panel` (FRAME 360×844)
    - `s4-detail-type` (FRAME 76×26)
      - `s4-detail-type-text` (TEXT: "● Concept")
    - `s4-detail-name` (TEXT: "GraphRAG")
    - `s4-detail-aliases` (TEXT: "aka  Graph-augmented RAG · KG-RAG · Microsoft Grap...")
    - `s4-detail-desc` (TEXT: "A retrieval-augmented generation paradigm that
con...")
    - `s4-detail-neigh-label` (TEXT: "NEIGHBORHOOD  ·  9 triples  ·  1-hop")
    - `s4-detail-neigh-list` (TEXT: "— uses_method   →  Leiden algorithm
— uses_method ...")
    - `s4-detail-cta` (FRAME 312×44)
      - `s4-detail-cta-text` (TEXT: "Ask about GraphRAG in Chat  →")
    - `s4-detail-evidence-label` (TEXT: "EVIDENCE  ·  47 chunks reference this entity")
    - `s4-detail-evidence-quote` (TEXT: ""...we observe that local search is appropriate
wh...")
    - `s4-detail-evidence-more` (TEXT: "Show all 47  →")
```

### S5 Review Generation (`15:296` — 1440×900)

```
- `[S5] Review Generation — Desktop 1440` (FRAME 1440×900)
  - `s5-topbar` (RECTANGLE 1440×56)
  - `s5-topbar-text` (TEXT: "◆ RAG-KG    ●  graphrag-survey  /  Review · GraphR...")
  - `s5-status-running` (FRAME 88×32)
    - `s5-status-text` (TEXT: "● Running")
  - `s5-runbg-link` (TEXT: "Run in bg  ↗")
  - `s5-progress-panel` (FRAME 320×784)
    - `s5-pipeline-title` (TEXT: "Pipeline")
    - `s5-pipeline-meta` (TEXT: "step 4 of 7  ·  04:18 elapsed  ·  ~03:30 left")
    - `s5-pipeline-tree` (TEXT: "◉  Decompose into subtopics
     412 tok  ·  3.2s
...")
    - `s5-pipeline-divider` (RECTANGLE 280×1)
    - `s5-runstats-label` (TEXT: "RUN STATS")
    - `s5-runstats-body` (TEXT: "Tokens used     14,328 / 32,000
Cost so far     $0...")
    - `s5-cancel-btn` (FRAME 130×40)
      - `s5-cancel-text` (TEXT: "Cancel run")
    - `s5-download-btn` (FRAME 142×40)
      - `s5-download-text` (TEXT: "↓  Download draft .md")
  - `s5-draft-panel` (FRAME 688×784)
    - `s5-draft-h1` (TEXT: "GraphRAG advances 2024–2025")
    - `s5-draft-meta` (TEXT: "Draft  ·  524 / 3,000 words  ·  29 citations  ·  g...")
    - `s5-draft-h2-1` (TEXT: "1. Pre-trained models for KG construction")
    - `s5-draft-p1-pre` (TEXT: "Recent work on GraphRAG has converged on the use o...")
    - `s5-cite-1` (FRAME 26×20)
      - `s5-cite-1-num` (TEXT: "1")
    - `s5-draft-p1-mid` (TEXT: "show that GPT-4o-mini achieves 0.81 triple precisi...")
    - `s5-draft-p1-line2` (TEXT: "on a curated MS academic-paper benchmark, while op...")
    - `s5-cite-2` (FRAME 26×20)
      - `s5-cite-2-num` (TEXT: "2")
    - `s5-draft-p1-after` (TEXT: ". Crucially, all leading methods now")
    - `s5-draft-p1-end` (TEXT: "embed provenance directly into triples, enabling t...")
    - `s5-draft-h2-2` (TEXT: "2. Hierarchical knowledge graphs")
    - `s5-draft-p2-pre` (TEXT: "Three architectural lineages dominate the 2024–202...")
    - `s5-cite-3` (FRAME 26×20)
      - `s5-cite-3-num` (TEXT: "3")
    - `s5-draft-p2-mid` (TEXT: "organises entities into Leiden communities at mult...")
    - `s5-cite-4` (FRAME 26×20)
      - `s5-cite-4-num` (TEXT: "4")
    - `s5-draft-p2-end` (TEXT: "replaces fixed C0–C3 levels with on-the-")
    - `s5-draft-streaming` (TEXT: "fly cluster discovery via top-down LLM critique. T...")
    - `s5-cursor` (RECTANGLE 2×16)
    - `s5-draft-streaming-meta` (TEXT: "Drafting subtopic 2  ·  Haiku 4.5  ·  324 / 800 to...")
    - `s5-draft-divider` (RECTANGLE 608×1)
    - `s5-draft-pending` (TEXT: "3.  Community summaries     ⏵ pending
4.  Eval & l...")
  - `s5-cite-panel` (FRAME 336×784)
    - `s5-cite-title` (TEXT: "Live citations")
    - `s5-cite-meta` (TEXT: "29 unique sources  ·  0 broken  ·  cross-checked")
    - `s5-cite-list` (TEXT: "[1]  Edge et al. 2024
       From Local to Global:...")
    - `s5-cite-more` (TEXT: "+ 22 more  →")
  - `s5-empty-state-note` (TEXT: "Empty state behavior: when 0 chunks match a subtop...")
```

### S6 Documents (`16:344` — 1440×900)

```
- `[S6] Documents — Desktop 1440` (FRAME 1440×900)
  - `s6-topbar` (RECTANGLE 1440×56)
  - `s6-topbar-text` (TEXT: "◆ RAG-KG    ●  graphrag-survey  /  Documents")
  - `s6-page-title` (TEXT: "Documents")
  - `s6-page-meta` (TEXT: "2,184 docs in graphrag-survey  ·  62.4k chunks  · ...")
  - `s6-upload-cta` (FRAME 168×44)
    - `s6-upload-cta-text` (TEXT: "↑  Upload PDFs")
  - `s6-dropzone` (FRAME 1376×120)
    - `s6-dropzone-title` (TEXT: "Drop PDFs, ZIPs, or folders here")
    - `s6-dropzone-meta` (TEXT: "Files attach to graphrag-survey  ·  parsing pipeli...")
    - `s6-dropzone-help` (TEXT: "or click "Upload PDFs" above  ·  resumable, idempo...")
  - `s6-table` (FRAME 1376×524)
    - `s6-table-header` (RECTANGLE 1376×48)
    - `s6-th-title` (TEXT: "TITLE")
    - `s6-th-year` (TEXT: "YEAR")
    - `s6-th-status` (TEXT: "STATUS")
    - `s6-th-chunks` (TEXT: "CHUNKS")
    - `s6-th-entities` (TEXT: "ENTITIES")
    - `s6-th-ingested` (TEXT: "INGESTED")
    - `s6-r1-title` (TEXT: "From Local to Global: A Graph RAG Approach to Quer...")
    - `s6-r1-meta` (TEXT: "Edge et al.  ·  Microsoft Research  ·  arXiv:2404....")
    - `s6-r1-year` (TEXT: "2024")
    - `s6-r1-status` (FRAME 76×22)
      - `s6-r1-status-text` (TEXT: "● Ready")
    - `s6-r1-chunks` (TEXT: "128")
    - `s6-r1-entities` (TEXT: "94")
    - `s6-r1-ingested` (TEXT: "3 days ago")
    - `s6-r1-divider` (RECTANGLE 1376×1)
    - `s6-r2-title` (TEXT: "Hierarchical Community Summaries for Knowledge Gra...")
    - `s6-r2-meta` (TEXT: "Liu et al.  ·  ACL 2025  ·  doi:10.18653/v1/acl.20...")
    - `s6-r2-year` (TEXT: "2025")
    - `s6-r2-status` (FRAME 76×22)
      - `s6-r2-status-text` (TEXT: "● Ready")
    - `s6-r2-chunks` (TEXT: "94")
    - `s6-r2-entities` (TEXT: "71")
    - `s6-r2-ingested` (TEXT: "3 days ago")
    - `s6-r2-divider` (RECTANGLE 1376×1)
    - `s6-r3-title` (TEXT: "Self-RAG: Learning to Retrieve, Generate, and Crit...")
    - `s6-r3-meta` (TEXT: "Wang, Asai et al.  ·  ICLR 2025  ·  arXiv:2310.115...")
    - `s6-r3-year` (TEXT: "2025")
    - `s6-r3-status` (FRAME 88×22)
      - `s6-r3-status-text` (TEXT: "◐ Indexing")
    - `s6-r3-progress-track` (RECTANGLE 88×3)
    - `s6-r3-progress-fill` (RECTANGLE 62×3)
    - `s6-r3-chunks` (TEXT: "— / 96")
    - `s6-r3-entities` (TEXT: "—")
    - `s6-r3-ingested` (TEXT: "2m ago · 70%")
    - `s6-r3-divider` (RECTANGLE 1376×1)
    - `s6-r4-title` (TEXT: "Adaptive Cluster Discovery in Knowledge Graphs (GR...")
    - `s6-r4-meta` (TEXT: "Liu, Sun et al.  ·  NeurIPS 2025  ·  arXiv:2509.02...")
    - `s6-r4-year` (TEXT: "2025")
    - `s6-r4-status` (FRAME 88×22)
      - `s6-r4-status-text` (TEXT: "◐ Parsing")
    - `s6-r4-progress-track` (RECTANGLE 88×3)
    - `s6-r4-progress-fill` (RECTANGLE 28×3)
    - `s6-r4-chunks` (TEXT: "— / —")
    - `s6-r4-entities` (TEXT: "—")
    - `s6-r4-ingested` (TEXT: "just now · 32%")
    - `s6-r4-divider` (RECTANGLE 1376×1)
    - `s6-r5-title` (TEXT: "MultiHop-RAG: A Benchmark for Multi-Hop Knowledge ...")
    - `s6-r5-meta` (TEXT: "Yang et al.  ·  scanned PDF · figures rejected by ...")
    - `s6-r5-year` (TEXT: "2024")
    - `s6-r5-status` (FRAME 88×22)
      - `s6-r5-status-text` (TEXT: "⊘ Failed")
    - `s6-r5-chunks` (TEXT: "—")
    - `s6-r5-entities` (TEXT: "—")
    - `s6-r5-retry` (TEXT: "↻ Retry with MinerU")
    - `s6-r5-divider` (RECTANGLE 1376×1)
    - `s6-more-rows` (TEXT: "… 2,179 more docs")
    - `s6-queue-summary` (TEXT: "Queue · 14 indexing · 3 parsing · 1 failed     ·  ...")
    - `s6-fail-popover` (FRAME 320×144)
      - `s6-fail-popover-title` (TEXT: "⊘ Parse error")
      - `s6-fail-popover-body` (TEXT: "Nougat detected scanned image-only PDF.
No text la...")
```

### S7 Reason + Hypothesize (`16:414` — 1440×900)

```
- `[S7] Cross-Paper Reasoning + Hypothesize — Desktop 1440` (FRAME 1440×900)
  - `s7-topbar` (RECTANGLE 1440×56)
  - `s7-topbar-text` (TEXT: "◆ RAG-KG    ●  graphrag-survey  /  Reasoning + Hyp...")
  - `s7-reason-h1` (TEXT: "Cross-paper reasoning")
  - `s7-reason-sub` (TEXT: "Multi-hop questions across the corpus, with KG pat...")
  - `s7-reason-q` (FRAME 672×88)
    - `s7-reason-q-text` (TEXT: "Did the GraphRAG team's community summarization ap...")
  - `s7-reason-reset` (TEXT: "Reset")
  - `s7-reason-run` (FRAME 144×36)
    - `s7-reason-run-text` (TEXT: "Find paths  →")
  - `s7-path-canvas` (FRAME 672×320)
    - `s7-path-title` (TEXT: "Best meta-path · 3 hops · confidence 0.78")
    - `s7-path-n1` (FRAME 112×52)
      - `s7-path-n1-label` (TEXT: "GraphRAG")
    - `s7-arrow-1` (TEXT: "— uses_method →")
    - `s7-path-n2` (FRAME 152×52)
      - `s7-path-n2-label` (TEXT: "Community summary")
    - `s7-arrow-2` (TEXT: "— extended_by →")
    - `s7-path-n3` (FRAME 128×52)
      - `s7-path-n3-label` (TEXT: "Tu et al. 2025")
    - `s7-arrow-3` (TEXT: "— evaluates_on →")
    - `s7-path-n4` (FRAME 152×52)
      - `s7-path-n4-label` (TEXT: "PrimeKG (biomedical)")
    - `s7-path-divider` (RECTANGLE 632×1)
    - `s7-conclusion-label` (TEXT: "CONCLUSION")
    - `s7-conclusion-body` (TEXT: "Yes — the Microsoft GraphRAG community-summarizati...")
  - `s7-evidence-timeline` (FRAME 672×252)
    - `s7-evidence-title` (TEXT: "Evidence timeline · 4 papers across the 3 hops")
    - `s7-evidence-body` (TEXT: "2024-04   Edge et al.    "Community summaries buil...")
    - `s7-evidence-cta` (TEXT: "Open all 4 in Chat  →")
  - `s7-hypo-h1` (TEXT: "Hypothesize")
  - `s7-hypo-sub` (TEXT: "Provide an entity pair. The system mines KG paths ...")
  - `s7-hypo-input-1` (FRAME 320×52)
    - `s7-hypo-input-1-label` (TEXT: "Entity A")
    - `s7-hypo-input-1-name` (TEXT: "● GraphRAG  (Concept)")
  - `s7-hypo-input-2` (FRAME 320×52)
    - `s7-hypo-input-2-label` (TEXT: "Entity B")
    - `s7-hypo-input-2-name` (TEXT: "● Drug repositioning  (Concept)")
  - `s7-hypo-result-meta` (TEXT: "5 candidate hypotheses · sorted by novelty × confi...")
  - `s7-hypo-card-1` (FRAME 656×180)
    - `s7-hypo-1-rank` (FRAME 36×22)
      - `s7-hypo-1-rank-text` (TEXT: "#1")
    - `s7-hypo-1-text` (TEXT: "Hierarchical KG community summaries can compress
b...")
    - `s7-hypo-1-novelty-label` (TEXT: "novelty")
    - `s7-hypo-1-novelty-track` (RECTANGLE 120×4)
    - `s7-hypo-1-novelty-fill` (RECTANGLE 102×4)
    - `s7-hypo-1-novelty-val` (TEXT: "0.85")
    - `s7-hypo-1-conf-label` (TEXT: "confidence")
    - `s7-hypo-1-conf-track` (RECTANGLE 120×4)
    - `s7-hypo-1-conf-fill` (RECTANGLE 86×4)
    - `s7-hypo-1-conf-val` (TEXT: "0.72")
    - `s7-hypo-1-verif-label` (TEXT: "verifiability")
    - `s7-hypo-1-verif-track` (RECTANGLE 120×4)
    - `s7-hypo-1-verif-fill` (RECTANGLE 94×4)
    - `s7-hypo-1-verif-val` (TEXT: "0.78")
    - `s7-hypo-1-paths` (TEXT: "3 supporting paths in KG · grounded in 4 papers · ...")
  - `s7-hypo-card-2` (FRAME 656×88)
    - `s7-hypo-2-text-1` (TEXT: "#2  ·  Multi-hop ToG over a drug-disease subgraph ...")
    - `s7-hypo-2-text-2` (TEXT: "8–12 pp on rare-disease repositioning, where corpu...")
    - `s7-hypo-2-meta` (TEXT: "novelty 0.71  ·  confidence 0.68  ·  verifiability...")
  - `s7-hypo-card-3` (FRAME 656×88)
    - `s7-hypo-3-text-1` (TEXT: "#3  ·  Adding a critic LLM that re-checks each ret...")
    - `s7-hypo-3-text-2` (TEXT: "recovers most of the Self-RAG benefit at one-third...")
    - `s7-hypo-3-meta` (TEXT: "novelty 0.62  ·  confidence 0.81  ·  verifiability...")
  - `s7-hypo-actions` (TEXT: "+ 2 more  ·  Save shortlist  ·  Export as JSON")
  - `s7-empty-state-note` (TEXT: "Empty state: if no path connects the two entities ...")
```

### S8 Eval Dashboard + Settings (`20:479` — 1440×900)

```
- `[S8] Eval Dashboard + Settings — Desktop 1440` (FRAME 1440×900)
  - `s8-topbar` (RECTANGLE 1440×56)
  - `s8-topbar-text` (TEXT: "◆ RAG-KG    ●  graphrag-survey  /  Eval & Settings")
  - `s8-eval-h1` (TEXT: "Evaluation dashboard")
  - `s8-eval-meta` (TEXT: "smoke (10) · multihop (32) · review (5)  ·  last 3...")
  - `s8-kpi-1` (FRAME 336×128)
    - `kpi-1-label` (TEXT: "VAR  ·  Valid Answer Rate")
    - `kpi-1-value` (TEXT: "76.4%")
    - `kpi-1-delta` (TEXT: "↑ 2.1pp / week")
    - `kpi-1-target` (TEXT: "target ≥ 75%  ·  v1.0 GA criterion  ·  ✓ on track")
  - `s8-kpi-1` (FRAME 336×128)
    - `kpi-1-label` (TEXT: "Citation F1  ·  claim-evidence")
    - `kpi-1-value` (TEXT: "0.872")
    - `kpi-1-delta` (TEXT: "↑ 0.04 / week")
    - `kpi-1-target` (TEXT: "target ≥ 0.85  ·  v1.0 GA criterion  ·  ✓ on track")
  - `s8-kpi-1` (FRAME 336×128)
    - `kpi-1-label` (TEXT: "P95 latency  ·  per question")
    - `kpi-1-value` (TEXT: "14.2s")
    - `kpi-1-delta` (TEXT: "↓ 1.8s / week")
    - `kpi-1-target` (TEXT: "target ≤ 20s  ·  v1.0 GA criterion  ·  ✓ on track")
  - `s8-kpi-1` (FRAME 336×128)
    - `kpi-1-label` (TEXT: "$ / question  ·  avg cost")
    - `kpi-1-value` (TEXT: "$0.084")
    - `kpi-1-delta` (TEXT: "↓ $0.012 / week")
    - `kpi-1-target` (TEXT: "target ≤ $0.10  ·  v1.0 GA criterion  ·  ✓ on trac...")
  - `s8-trend-panel` (FRAME 864×280)
    - `s8-trend-title` (TEXT: "VAR  ·  daily ·  last 30 days")
    - `s8-trend-meta` (TEXT: "smoke set · 10-question rolling window · target li...")
    - `bar-d1` (FRAME 56×80)
    - `bar-d2` (FRAME 56×86)
    - `bar-d3` (FRAME 56×78)
    - `bar-d3` (FRAME 56×78)
    - `bar-d4` (FRAME 56×92)
    - `bar-d5` (FRAME 56×100)
    - `bar-d6` (FRAME 56×108)
    - `bar-d7` (FRAME 56×102)
    - `bar-d8` (FRAME 56×124)
    - `bar-d9` (FRAME 56×138)
    - `bar-d10` (FRAME 56×150)
    - `bar-d11` (FRAME 56×162)
    - `bar-d12` (FRAME 56×180)
    - `s8-target-line` (RECTANGLE 800×1)
    - `s8-target-label` (TEXT: "75%")
    - `s8-x-axis` (TEXT: "May 1            May 8           May 15          M...")
  - `s8-settings-panel` (FRAME 496×552)
    - `s8-settings-title` (TEXT: "Library settings")
    - `s8-settings-meta` (TEXT: "graphrag-survey  ·  per-Library overrides shown he...")
    - `s8-models-label` (TEXT: "MODELS")
    - `s8-llm-label` (TEXT: "LLM router")
    - `s8-llm-select` (FRAME 272×32)
      - `s8-llm-select-text` (TEXT: "Local Qwen2.5-32B  →  Haiku 4.5  →  Sonnet 4.6   ▾")
    - `s8-embed-label` (TEXT: "Embedder")
    - `s8-embed-select` (FRAME 272×32)
      - `s8-embed-select-text` (TEXT: "BGE-M3  ·  4096 dim  ·  local                     ...")
    - `s8-set-divider-1` (RECTANGLE 448×1)
    - `s8-budget-label` (TEXT: "BUDGET  ·  per question")
    - `s8-budget-list` (TEXT: "Max retrieval steps      8
Max LLM calls          ...")
    - `s8-set-divider-2` (RECTANGLE 448×1)
    - `s8-data-label` (TEXT: "DATA")
    - `s8-export-btn` (FRAME 216×36)
      - `s8-export-text` (TEXT: "↓ Export Library...")
    - `s8-purge-btn` (FRAME 216×36)
      - `s8-purge-text` (TEXT: "⊗ Purge Library (irreversible)")
    - `s8-purge-help` (TEXT: "Drops every Qdrant collection, Neo4j DB, BM25 inde...")
  - `s8-failures` (FRAME 864×248)
    - `s8-failures-title` (TEXT: "Recent eval failures  ·  click to inspect trace in...")
    - `s8-failures-th` (TEXT: "QID       SET           QUESTION (truncated)      ...")
    - `s8-failures-rows` (TEXT: "multihop-027   multihop   "Did GraphRAG outperform...")
    - `s8-failures-more` (TEXT: "View all 14 failures in Langfuse  →")
  - `s8-lib-filter` (FRAME 268×36)
    - `s8-lib-filter-text` (TEXT: "Filter:  ●  graphrag-survey                       ...")
  - `s8-alert-banner` (FRAME 1376×12)
  - `s8-alert-text` (TEXT: "●  All KPIs within target  ·  last alert 9 days ag...")
```

### M1 LibraryCreateModal (`21:548` — 600×640)

```
- `[M1] LibraryCreateModal` (FRAME 600×640)
  - `m1-title` (TEXT: "Create a new Library")
  - `m1-subtitle` (TEXT: "Each Library is a fully isolated namespace.
Docume...")
  - `m1-slug-label` (TEXT: "Library ID  ·  slug")
  - `m1-slug-input` (FRAME 536×44)
    - `m1-slug-value` (TEXT: "graphrag-survey")
  - `m1-slug-help` (TEXT: "lowercase, digits, hyphens · 3–30 chars · permanen...")
  - `m1-name-label` (TEXT: "Display name")
  - `m1-name-input` (FRAME 536×44)
    - `m1-name-value` (TEXT: "GraphRAG Survey")
  - `m1-desc-label` (TEXT: "Description")
  - `m1-desc-input` (FRAME 536×72)
    - `m1-desc-value` (TEXT: "GraphRAG, graph-based retrieval, and multi-hop
rea...")
  - `m1-lang-label` (TEXT: "Primary language")
  - `m1-lang-en` (FRAME 120×36)
    - `m1-lang-en-text` (TEXT: "English")
  - `m1-lang-zh` (FRAME 120×36)
    - `m1-lang-zh-text` (TEXT: "中文")
  - `m1-lang-mixed` (FRAME 120×36)
    - `m1-lang-mixed-text` (TEXT: "Mixed (zh + en)")
  - `m1-init-help` (TEXT: "Will initialize: Qdrant collection · Neo4j composi...")
  - `m1-cancel-btn` (FRAME 100×40)
    - `m1-cancel-text` (TEXT: "Cancel")
  - `m1-create-btn` (FRAME 136×40)
    - `m1-create-text` (TEXT: "Create Library  →")
```

### M2 DeleteConfirmModal (`22:573` — 600×560)

```
- `[M2] DeleteConfirmModal` (FRAME 600×560)
  - `m2-icon-bg` (FRAME 48×48)
    - `m2-icon` (TEXT: "⚠")
  - `m2-title` (TEXT: "Purge "graphrag-survey"?")
  - `m2-subtitle` (TEXT: "This action is irreversible. The Library and all i...")
  - `m2-impact-card` (FRAME 536×144)
    - `m2-impact-label` (TEXT: "YOU WILL LOSE")
    - `m2-impact-list` (TEXT: "●  2,184 documents (62.4k chunks)
●  Knowledge gra...")
  - `m2-confirm-label` (TEXT: "Type "graphrag-survey" to confirm")
  - `m2-confirm-input` (FRAME 536×44)
    - `m2-confirm-value` (TEXT: "graphrag-survey")
  - `m2-confirm-help` (TEXT: "Match must be exact (case-sensitive). Delete butto...")
  - `m2-cancel-btn` (FRAME 100×40)
    - `m2-cancel-text` (TEXT: "Cancel")
  - `m2-purge-btn` (FRAME 136×40)
    - `m2-purge-text` (TEXT: "⊗  Purge Library")
```

### M3 CommandPaletteOverlay (`22:589` — 720×560)

```
- `[M3] CommandPaletteOverlay` (FRAME 720×560)
  - `m3-input-row` (FRAME 720×64)
    - `m3-search-icon` (TEXT: "🔍")
    - `m3-search-query` (TEXT: "community")
    - `m3-esc-hint` (TEXT: "esc")
  - `m3-divider-1` (RECTANGLE 720×1)
  - `m3-section-1` (TEXT: "ENTITIES IN graphrag-survey")
  - `m3-result-active` (FRAME 704×36)
    - `m3-r1-text` (TEXT: "●  Community detection")
    - `m3-r1-meta` (TEXT: "Method · 248 references")
    - `m3-r1-action` (TEXT: "go to KG  ↵")
  - `m3-r2` (TEXT: "●  Community summarization                Method ·...")
  - `m3-r3` (TEXT: "●  Hierarchical communities (C0–C3)    Concept · 9...")
  - `m3-section-2` (TEXT: "DOCUMENTS")
  - `m3-doc-list` (TEXT: "📄  Hierarchical Community Summaries for KG QA   Li...")
  - `m3-section-3` (TEXT: "ACTIONS")
  - `m3-actions` (TEXT: "⌘ R    Generate review on "community summarization...")
  - `m3-divider-2` (RECTANGLE 720×1)
  - `m3-footer-hint` (TEXT: "↑ ↓ navigate     ↵ open     tab cycle scope     ⌘ ...")
```

### M4 DocumentDetailDrawer (`23:13` — 800×900)

```
- `[M4] DocumentDetailDrawer` (FRAME 800×900)
  - `m4-title` (TEXT: "From Local to Global: A Graph RAG
Approach to Quer...")
  - `m4-meta` (TEXT: "Edge, Trinh, Cheng, Bradley, Chao, Mody, Truitt, L...")
  - `m4-status-pill` (FRAME 88×28)
    - `m4-status-text` (TEXT: "● Ready")
  - `m4-stat-chunks` (TEXT: "128")
  - `m4-stat-chunks-label` (TEXT: "chunks")
  - `m4-stat-entities` (TEXT: "94")
  - `m4-stat-entities-label` (TEXT: "entities")
  - `m4-stat-triples` (TEXT: "218")
  - `m4-stat-triples-label` (TEXT: "triples")
  - `m4-stat-pages` (TEXT: "22")
  - `m4-stat-pages-label` (TEXT: "pages")
  - `m4-pdf-preview` (FRAME 336×408)
    - `m4-pdf-placeholder` (TEXT: "📄  page 1 of 22")
    - `m4-pdf-label` (TEXT: "PDF preview")
  - `m4-sections-label` (TEXT: "SECTIONS  ·  12")
  - `m4-sections-list` (TEXT: "1   Abstract                                      ...")
  - `m4-chunks-label` (TEXT: "CHUNKS  ·  showing 3 of 128  ·  filter by section")
  - `m4-chunks-list` (TEXT: "chunk_2871   §4.5 · p.4   "...we observe that loca...")
  - `m4-action-reparse` (FRAME 152×40)
    - `m4-reparse-text` (TEXT: "↻  Re-parse")
  - `m4-action-cite` (FRAME 200×40)
    - `m4-cite-text` (TEXT: "Open in Chat / Ask  →")
  - `m4-action-delete` (FRAME 152×40)
    - `m4-delete-text` (TEXT: "Remove document")
```

