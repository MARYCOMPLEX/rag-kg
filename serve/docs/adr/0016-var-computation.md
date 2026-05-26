# ADR-0016: VAR (Valid Answer Rate) Computation

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: PRD §3.1 North Star instrumentation; BACKEND_ROADMAP §3.2 Gap 4 + §3.3 Gap 5
**Related**: ADR-0007 (Error Envelope), ADR-0011 (Notification),
ADR-0015 (Cost Cap), ADR-0021 (Eval Alerting), ADR-0008 (Context Management)

## Context

PRD §3.1 nominates **Valid Answer Rate (VAR)** as the project's North Star:

> 用户提问 → 收到带引用答案 → 用户标记"有用 + 引用正确" 的比例。
> 目标：v1.0 达成 ≥ 75 %。

PRD §18.3 binds GA gates to it:

| Stage    | VAR target |
|----------|------------|
| 外部 α   | ≥ 0.60     |
| β        | ≥ 0.70     |
| GA       | ≥ 0.75     |

But the *literal* PRD definition assumes **abundant user feedback**. In v1
the user base is 5 α testers ramping to 30 β users; on a typical day a
single Library may receive 10 questions, of which only 3 get explicit
feedback. With samples that small, the VAR estimate has confidence
intervals so wide that PR-blocking thresholds cannot be derived from it.

Meanwhile the test team needs a **CI-grade** signal: every PR must produce
a VAR number to vet against PRD §3.1. CI runs against the `qa.smoke.v1`
gold set, which has no human user — only deterministic synthetic queries.

The problem decomposes:

1. **What does VAR mean** in CI vs production?
2. **What sources** produce the binary "useful + citations correct"
   signal — humans, LLM-judges, both?
3. **How do we combine** sparse human feedback with dense LLM-judge output
   without one drowning the other?
4. **At what cadence** is VAR refreshed — per-feedback (real-time) or per
   day (snapshot)?
5. **What time window** counts? Trailing 7 d / 30 d / since last release?

PRD §13.5 explicitly flags `LLM-Judge 不稳定 — 双 LLM 独立打分取均值；定期人工校准`
as the mitigation for judge noise. PRD §16.2 mandates `银牌集（LLM-Judge）`
as a first-class evaluation tier.

`BACKEND_ROADMAP §3.3 Gap 5` defines the `AnswerFeedback` model and
endpoint; this ADR locks the *aggregation rules*.

## Decision

### 1. Two-tier VAR with feedback-priority + judge-fallback

Define **three** VAR variants, each computed independently and exposed
side-by-side:

| Variant         | Source                              | When trustworthy           |
|-----------------|-------------------------------------|----------------------------|
| `var_feedback`  | `AnswerFeedback` rows (human)       | sample size ≥ N_min        |
| `var_judge`     | LLM-judge on every answered query   | always (with confidence)   |
| `var_blended`   | Weighted combination, see §3        | always (the public number) |

The **public** VAR — the one displayed on the Eval Dashboard, the one
gating GA — is `var_blended`. Both `var_feedback` and `var_judge` are
shown beneath it for transparency.

### 2. Feedback model and endpoint

```python
# packages/core/models.py
class AnswerFeedback(BaseModel):
    library_id:        str
    answer_id:         str         # FK to AnsweredQuery
    user_id:           str | None  # None for anonymous deployments
    useful:            bool
    citations_correct: bool
    comment:           str | None = None
    created_at:        datetime
    revoked_at:        datetime | None = None  # supports undo
```

```sql
CREATE TABLE answer_feedback (
    id                  BIGSERIAL PRIMARY KEY,
    library_id          TEXT      NOT NULL,
    answer_id           TEXT      NOT NULL,
    user_id             TEXT,
    useful              BOOLEAN   NOT NULL,
    citations_correct   BOOLEAN   NOT NULL,
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at          TIMESTAMPTZ,
    UNIQUE (answer_id, user_id)            -- one feedback per (answer, user)
);
CREATE INDEX answer_feedback_lib_date_idx
    ON answer_feedback (library_id, created_at DESC)
    WHERE revoked_at IS NULL;
```

Endpoints:

```
POST /v1/libraries/{lib}/qa/{answer_id}/feedback
  body: { useful: bool, citations_correct: bool, comment?: str }
  → 201 Created

DELETE /v1/libraries/{lib}/qa/{answer_id}/feedback
  → 204 No Content    (sets revoked_at; allows users to undo a misclick)
```

Re-submission updates the existing row (idempotent on `(answer_id, user_id)`).

### 3. Computation formulas

```
var_feedback(library_id, window) =
    | { f ∈ feedbacks(library_id, window) | f.useful AND f.citations_correct AND f.revoked_at IS NULL } |
    / | feedbacks(library_id, window) |        (denominator excludes revoked)

var_judge(library_id, eval_set, window) =
    | { snap ∈ eval_snapshots | snap.metric='judge_useful_AND_citations_correct'
                                AND snap.eval_set = eval_set
                                AND snap.date ∈ window
                                AND snap.value = 1 } |
    / | eval_snapshots(eval_set, window) |

var_blended(library_id, window) =
    let n_fb = | feedbacks(library_id, window) |
        w_fb = min(1.0, n_fb / N_FEEDBACK_FULL_TRUST)        # ramp 0..1 as samples grow
        w_jd = 1 - w_fb
    in  w_fb * var_feedback + w_jd * var_judge
```

Constants (in `packages/evaluation/var.py`):

```python
N_FEEDBACK_FULL_TRUST: int = 30   # at 30 feedbacks the judge weight = 0
N_FEEDBACK_DISPLAY_MIN: int =  5  # below this, var_feedback is hidden
DEFAULT_WINDOW_DAYS: int = 7
JUDGE_AGREEMENT_THRESHOLD: float = 0.6  # cross-judge agreement (§4)
```

The ramp `w_fb = min(1.0, n_fb / 30)` linearly hands trust from judge to
human as feedback accumulates. With 30 + feedbacks the judge contribution
is zero; below 30 the judge fills the gap.

The **denominator** is "answered queries that produced a non-empty answer
with citations" — empty-state responses (per BACKEND_ROADMAP §3.3 Gap 6)
are excluded so the metric measures *quality of attempted answers*, not
*coverage*. Empty rate is tracked as a separate KPI.

Refused tasks (per ADR-0015 cost block) **do** count: they are conceptually
"answered with `useful=False, citations_correct=False`" because the user
asked a question and got nothing useful.

### 4. LLM-judge implementation

PRD §13.5 mitigation: dual-LLM independent scoring, take the mean, and
**only count agreement**.

```python
class JudgeVerdict(BaseModel):
    answer_id:           str
    judge_model:         str     # e.g. "deepseek-v4-flash" / "claude-haiku-4-5"
    useful:              bool
    citations_correct:   bool
    rationale:           str
    score_confidence:    float   # judge self-reported [0,1]

def aggregate_judges(verdicts: list[JudgeVerdict]) -> JudgeAggregate:
    """Two judges; both must agree on the binary verdict to count."""
    a, b = verdicts
    agreed = (a.useful == b.useful) and (a.citations_correct == b.citations_correct)
    if not agreed or a.score_confidence < 0.6 or b.score_confidence < 0.6:
        return JudgeAggregate(verdict_useful=None, verdict_citations=None, agreed=False)
    return JudgeAggregate(
        verdict_useful=a.useful,
        verdict_citations=a.citations_correct,
        agreed=True,
    )
```

**Disagreement is treated as missing data**, not as 0.5. Disagreement
count is itself a metric (`var_judge_disagreement_rate`) — high values
flag judge instability and demand human calibration (PRD §13.5).

Judge prompts live in `packages/evaluation/judges/prompts.py`, version-locked
(`PROMPT_VERSION = "v2026-05"`). Changing prompts forces re-running the
judge over historic answers; we record `prompt_version` per verdict so
mixed-version data is filtered out of any single window.

### 5. Cadence: daily snapshot, real-time dashboard cache invalidation

```
+------------------------+               +------------------------+
| Worker cron 02:00 UTC  |               | API request            |
| eval_snapshot_job      |               | GET .../eval/kpis       |
+----------+-------------+               +----------+-------------+
           |                                        |
           v                                        v
+------------------------+               +------------------------+
| Run smoke set against  |               | Read eval_snapshots    |
| current QA pipeline    |               | for (library, window)  |
| Score with dual judges |               | Apply var_blended      |
| Insert eval_snapshots  |               | Cached 60 s in Redis   |
+------------------------+               +------------------------+
```

```sql
CREATE TABLE eval_snapshots (
    library_id  TEXT        NOT NULL,
    date        DATE        NOT NULL,
    eval_set    TEXT        NOT NULL,        -- 'smoke' | 'multihop' | 'review'
    metric      TEXT        NOT NULL,        -- 'var_judge' | 'citation_f1' | 'p95_latency' | ...
    value       NUMERIC     NOT NULL,
    sample_size INTEGER     NOT NULL,
    extra       JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (library_id, date, eval_set, metric)
);
```

Real-time invalidation: when a new `AnswerFeedback` row is written, we
invalidate the Redis key `var:{library_id}:{window}` (TTL 60 s).
Subsequent dashboard polls recompute. We deliberately do **not** publish
SSE updates for VAR — the dashboard is not a real-time game; minute-level
freshness is plenty.

Daily snapshot is the **only** authoritative source for trend charts and
PR alerts; ad-hoc real-time computations are for the live Settings/Eval
panels only.

### 6. Per-eval-set bucketing

PRD §13.2 partitions eval sets by task: `qa.smoke.v1`, `qa.multihop.v1`,
`review.v1`. VAR is reported per eval-set:

```
GET /v1/libraries/{lib}/eval/kpis?eval_set=smoke&days=7
  → {
      "var": {
        "blended":  0.792,
        "feedback": { "value": 0.83, "n": 24 },
        "judge":    { "value": 0.77, "n": 70, "disagreement_rate": 0.04 },
        "blend_weights": { "feedback": 0.80, "judge": 0.20 }
      },
      "citation_f1":     0.872,
      "p95_latency_s":  14.2,
      "avg_cost_usd":    0.084,
      "delta_7d":        { "var": +0.012, ... }
    }
```

The PRD GA gate (`VAR ≥ 0.75`) is evaluated against the **smoke** eval
set's `blended` value over a 30-day window — the largest possible window
that still reflects current model behaviour given M-class release cadence.

### 7. Time window

| Use case             | Window        | Rationale                                                   |
|----------------------|---------------|-------------------------------------------------------------|
| Settings panel       | 7 d trailing  | Recent enough to react; long enough to smooth               |
| Eval Dashboard       | 7 / 30 d toggle | User choice                                               |
| GA gate (PRD §18.3)  | 30 d trailing | Large enough for statistical credibility                    |
| PR check             | smoke set, single run | CI-deterministic                                    |
| Alerting (ADR-0021)  | 7 d vs prior 7 d | Catches regressions within one release cycle             |

Custom windows are supported via `?since=...&until=...` for ad-hoc analysis;
they bypass the snapshot cache and recompute on demand (rate-limited).

## Consequences

### Positive

- **Bridges sparse-feedback gap**: VAR is meaningful from day one (judge
  fills) and improves as user adoption grows (feedback takes over).
- **PRD §13.5 satisfied**: dual-judge with agreement gating, disagreement
  surfaced as its own metric.
- **CI-friendly**: every PR run produces a deterministic `var_judge` against
  the smoke set; PR comment can show before/after.
- **Self-calibrating**: high judge-disagreement automatically downweights
  the judge contribution, surfacing the need for human calibration.

### Negative

- **Three numbers** instead of one — UI must explain `feedback / judge / blended`.
  Mitigated by making `blended` visually primary and the others collapsible.
- **Prompt-version sensitivity**: a judge-prompt rewrite invalidates the
  trend until a new window of snapshots accumulates (~7 days). We pre-flight
  prompt changes in PRs that include parallel snapshot data.
- **30-day window in M7** is shorter than ideal for ML-style A/B testing,
  but adequate for the rolling-release model.

### Risks

- **R-VAR-1**: judge LLMs systematically biased relative to humans (e.g.
  always agreeing with verbose answers). **Mitigation**: monthly 50-sample
  human calibration; if `|var_judge - var_human| > 0.10` over 50 samples,
  prompt is regressed and an ADR amendment is filed. (PRD §13.5 mandate.)
- **R-VAR-2**: feedback is gameable / spammed by a single user.
  **Mitigation**: `(answer_id, user_id)` UNIQUE constraint; rate-limit per
  user per day; future moderation if multi-tenant ships.
- **R-VAR-3**: empty-state exclusion + cost-block inclusion creates
  inconsistent semantics. **Mitigation**: `var_definition` doc page in the
  Operator Runbook with worked examples; UI tooltip cites the doc.
- **R-VAR-4**: `N_FEEDBACK_FULL_TRUST = 30` is set by analogy, not data.
  **Mitigation**: monitor `var_feedback - var_judge` divergence; tune
  constant after 90 days of production data.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| **Feedback-only**, hide judge | PRD GA gate cannot be evaluated until ~hundreds of feedbacks accumulate; CI-blocking impossible. |
| **Judge-only**, ignore humans | Wastes the highest-signal data we have; PRD §3.1 *literal* definition includes user labels. |
| **Per-answer real-time VAR** | A single binary outcome is not a rate; aggregation is the metric. We do log per-answer `useful_AND_citations_correct` as the atomic event for trend computation. |
| **Hard threshold + binary blend (`if n_fb >= 30: feedback else judge`)** | Step function creates a visible jump on the dashboard the day feedback crosses 30. Linear ramp is smoother and equally simple. |
| **Single judge** | PRD §13.5 explicitly mandates dual judge. |
| **Take judge mean even on disagreement** | Hides instability; biases toward 0.5; against the PRD mitigation philosophy. |
| **Embed VAR in every QA response** | Confuses users — VAR is an aggregate KPI, not a per-answer property. |

## Open Questions

- **Q1**: When user provides `useful=True, citations_correct=False`, how
  much weight should that get? **Tentative**: counted as `useful AND citations`
  meaning `False` (both must be true). The two booleans together — not
  averaged — match the PRD literal definition.
- **Q2**: Should we compute a **lower-bound** Wilson confidence interval
  for `var_blended` instead of point estimate? Useful for small samples,
  but exposes a number users may not understand. **Tentative**: show
  bands on the dashboard chart, not in the headline number.
- **Q3**: How are conversation-level (multi-turn) feedbacks attributed?
  Per-turn? Per-conversation? **Tentative**: per-turn (`answer_id` is per-turn);
  conversation rollup is computed but secondary.
- **Q4**: Should refused tasks (cost-blocked) be included in the denominator?
  This ADR says **yes**, but it might be more intuitive to track separately
  as `refusal_rate`. We can flip this in a v1.1 amendment if α-tester
  feedback indicates confusion.

## Relationship to Other ADRs

- **ADR-0007 (Error Envelope)**: feedback endpoint uses standard error
  envelope; `revoke` returns 204 with no body.
- **ADR-0011 (Notification)**: when `var_feedback` drops below
  `var_judge - 0.10` (judge thinks we're better than users say), alerts via
  `notification_type=alert_triggered` with severity=warning.
- **ADR-0015 (Cost Cap)**: refused tasks count as failed VAR cases;
  a Library that constantly hits its cap will see VAR regress, which is a
  *correct* signal — the user is not getting answers.
- **ADR-0021 (Eval Alerting)**: VAR is the primary alert metric; trigger
  rule is *7-day rolling vs prior 7-day rolling > 5pp drop*, computed on
  `var_blended` over the smoke set.
- **ADR-0008 (Context Management)**: per-turn `answer_id` is generated by
  the conversation pipeline; feedback joins through it.
- **ADR-0003 (Library as Data Partition)**: all feedback / snapshot tables
  partition on `library_id`; cross-Library aggregation is L5-only per §16.6.
- **ADR-0022 (Library Purge)**: `answer_feedback` and `eval_snapshots` are
  cleaned by `purge_library`.

## References

- PRD §3.1 (North Star — VAR definition)
- PRD §3.2 (Guardrails — Citation F1 ≥ 0.85, P95 ≤ 20s — sibling metrics)
- PRD §13.2 (eval-set partitioning)
- PRD §13.5 (LLM-Judge mitigation — dual-judge mandate)
- PRD §16.2 (评测体系演进 — gold/silver buckets)
- PRD §18.3 (α/β/GA gates)
- BACKEND_ROADMAP §3.2 Gap 4 (Quality KPI panel — VAR computation)
- BACKEND_ROADMAP §3.3 Gap 5 (AnswerFeedback model + endpoint)
- BACKEND_ROADMAP §3.8 Gap 1 (eval_snapshots table + cron job)
- BACKEND_ROADMAP §7 BR04 (VAR sample sparsity risk — this ADR's primary
  driver)
