# Notifications Aggregation Performance Runbook

**Status**: planning / pre-baseline (no production load yet)
**Owner**: backend
**Tracks**: ADR_REVIEW §11.4
**Related**: ADR-0011 (notification center), `apps/api/_notification_reader.py`,
`migrations/versions/m7_010_notifications.py`

> This document defines the **expected** query plans, indexes, alarm
> thresholds, and fallback ladder for `/v1/notifications` and the
> top-bar unread badge under high cardinality. It is **not** a postmortem —
> the baseline numbers below are pre-recorded targets, not measurements.

---

## 1. Endpoints under audit

| Endpoint | Underlying SQL | Hot path? |
|---|---|---|
| `GET /v1/notifications` (list) | `_notification_reader.list_for_libraries` | yes — top-bar drawer open |
| `GET /v1/notifications/unread_count` | `_notification_reader.count_unread` | yes — every page load + SSE pulse |
| `POST /v1/notifications/{id}/read` | UPDATE by id | low (one row) |

The two hot SELECTs are the focus of this document.

## 2. Schema and index inventory

From `migrations/versions/m7_010_notifications.py` the `notifications`
table carries:

- PK: `id TEXT` (ULID)
- Cascade FK: `library_id → libraries.library_id ON DELETE CASCADE`
- Indexes:
  - `notifications_unread_idx` — partial `(created_at) WHERE read = FALSE`
  - `notifications_library_unread_idx` — partial `(library_id, created_at) WHERE read = FALSE`
  - `notifications_expires_idx` — `(expires_at)`

The two partial indexes on `read = FALSE` are the load-bearing pieces:
the unread count is the dominant query and an unread row is by far the
minority over the table's lifetime.

## 3. Expected query plans (target shapes)

### 3.1 `count_unread`

```sql
SELECT count(*) AS c
FROM notifications
WHERE read = FALSE
  AND expires_at > now()
  AND (library_id IS NULL OR library_id = ANY(:library_ids));
```

**Target plan**:

```
Aggregate
  -> Bitmap Heap Scan on notifications
       Recheck Cond: ((library_id = ANY (...)) OR (library_id IS NULL))
       Filter: (expires_at > now())
       -> BitmapOr
            -> Bitmap Index Scan on notifications_library_unread_idx
            -> Bitmap Index Scan on notifications_unread_idx
                  (filter: library_id IS NULL captured by recheck)
```

**Red flag**: a Seq Scan on the table. If the planner picks one, recheck
`pg_stat_user_tables.last_analyze` — partial-index selectivity estimates
need fresh `ANALYZE` to be trusted.

### 3.2 `list_for_libraries`

```sql
SELECT ...
FROM notifications
WHERE (library_id IS NULL OR library_id = ANY(:library_ids))
  AND expires_at > now()
  AND (NOT :unread_only OR read = FALSE)
  AND (:since::timestamptz IS NULL OR created_at >= :since)
ORDER BY created_at DESC
LIMIT :limit;
```

**Target plan (`unread_only = TRUE`)** — same partial indexes feed an
ORDER-BY pre-sorted by `created_at`:

```
Limit
  -> Index Scan Backward on notifications_library_unread_idx
       Filter: expires_at > now() AND (since clause)
```

**Target plan (`unread_only = FALSE`)** — falls back to a sort over the
visible window. With p99 read-count ≈ 100 rows per drawer this is
cheap, but past 1 M total rows we expect:

```
Limit
  -> Sort  (top-N heapsort, work_mem≤4MB)
       -> Bitmap Heap Scan on notifications
            -> BitmapOr
                 -> Bitmap Index Scan on notifications_library_unread_idx
                      Index Cond: library_id = ANY(...)
                 -> Bitmap Index Scan on (library_id IS NULL fallback)
```

If the sort spills to disk under 1 M rows we have an index gap — see
§5 fallback ladder.

## 4. Alarm thresholds (proposed; not yet tripped)

| Signal | Source | Warn | Crit |
|---|---|---|---|
| p95 latency on `count_unread` | OTEL span `api.notifications.count_unread` | > 50 ms | > 200 ms |
| p95 latency on `list_for_libraries` | OTEL span `api.notifications.list_for_libraries` | > 100 ms | > 500 ms |
| Rows scanned per call | `pg_stat_statements` | > 10 000 | > 100 000 |
| Unread badge fan-out | top-bar pulse rate | > 10 RPS / user | > 30 RPS / user |
| `notifications_unread_idx` size | `pg_relation_size` | > 200 MB | > 1 GB |

These map to ADR-0021 alert candidates but are **not** wired yet.

## 5. Fallback ladder (when thresholds breach)

Apply in this order — each step is deployable independently and
strictly less invasive than the next.

### Step 1 — Pagination cursor instead of OFFSET

The current SELECT already uses `LIMIT` only (no OFFSET), so this is a
no-op. If a future PR adds OFFSET, switch to keyset pagination on
`(created_at, id)` to avoid `Index Scan + skip` blow-ups.

### Step 2 — Redis cache for the unread badge

Wrap `count_unread` with a 5-second Redis TTL keyed by
`notif:unread:{principal_hash}`. Trade staleness for cardinality:
the top-bar dot is fundamentally an approximation. Invalidation hooks
already exist on `POST /notifications/{id}/read`.

Implementation seam: `apps/api/_notification_reader.py` accepts a
``cache: NotificationCountCache | None = None`` argument. The cache
adapter lives next to `apps/api/_internal/` style modules.

### Step 3 — Drop polling, force SSE pull-only

ADR-0011 already specifies the SSE channel `/v1/notifications/stream`.
Remove the periodic `count_unread` poll from the frontend; the SSE
stream drives the badge counter via incremental `+1 / -1` deltas.

This requires:

- ADR-0011 §SSE event payload extended with a `delta: int` field
- frontend `useNotificationsStore` switching from poll to subscribe
- a one-time recount on tab focus to recover from missed events

### Step 4 — Materialised view for the global view

Last resort. Add `notifications_unread_summary` materialised view
refreshed every 30 s, partitioned by `library_id`. Requires Alembic
migration + cron job. Trade real-time for correctness.

## 6. k6 / locust skeletons (do **not** run in CI)

These are templates only. The repo does not yet have a load testing
target; running these requires a staging Postgres with realistic data
volume.

### 6.1 k6 outline

```javascript
// k6 run --env BASE_URL=https://staging.api.example.com perf/notifications.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    badge: {
      executor: 'constant-arrival-rate',
      rate: 1000,           // 1000 RPS for the unread count
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 200,
      exec: 'badge',
    },
    drawer: {
      executor: 'constant-arrival-rate',
      rate: 50,             // 50 RPS for the drawer list
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 50,
      exec: 'drawer',
    },
  },
  thresholds: {
    'http_req_duration{scenario:badge}': ['p(95)<50', 'p(99)<200'],
    'http_req_duration{scenario:drawer}': ['p(95)<100', 'p(99)<500'],
  },
};

export function badge() {
  const res = http.get(`${__ENV.BASE_URL}/v1/notifications/unread_count`);
  check(res, { '200': r => r.status === 200 });
}

export function drawer() {
  const res = http.get(
    `${__ENV.BASE_URL}/v1/notifications?unread_only=true&limit=20`,
  );
  check(res, { '200': r => r.status === 200 });
  sleep(0.1);
}
```

### 6.2 locust outline

```python
# locust -f perf/notifications.py --host https://staging.api.example.com
from locust import HttpUser, between, task


class NotificationUser(HttpUser):
    wait_time = between(0.1, 1.0)

    @task(20)
    def badge(self) -> None:
        self.client.get("/v1/notifications/unread_count", name="badge")

    @task(1)
    def drawer(self) -> None:
        self.client.get(
            "/v1/notifications?unread_only=true&limit=20",
            name="drawer",
        )
```

## 7. Synthetic data preparation

To exercise the > 1 M row regime use:

```sql
INSERT INTO notifications (id, library_id, type, severity, title,
                           body, payload, read, created_at, expires_at)
SELECT
  encode(gen_random_bytes(16), 'hex'),
  CASE WHEN random() < 0.05 THEN NULL
       ELSE 'lib-' || (1 + (random() * 50)::int)
  END,
  'task_completed',
  'info',
  'Synthetic ' || g,
  NULL,
  '{}'::jsonb,
  random() < 0.95,                                -- 95 % already read
  now() - (random() * interval '90 days'),
  now() + interval '30 days'
FROM generate_series(1, 1000000) g;
ANALYZE notifications;
```

5 % unread × 1 M rows = 50 000 unread rows. The partial index
`notifications_unread_idx` therefore stores ~50 000 entries, a few
megabytes — well within the warn band of §4.

## 8. Open questions

1. Per-user feed: today the reader assumes the principal sees every
   notification scoped to their library set. If we add per-user
   targeting (`recipient_principal_id`), the index strategy needs a
   refresh — likely a third partial `(recipient_principal_id, created_at)
   WHERE read = FALSE`.
2. Multi-tenant noisy neighbours: a single library producing 100 000
   notifications/day would skew the partial index. Consider a hard cap
   per-library-per-day at the writer (already present in
   `cost.daily_cap` for LLM cost — analogous knob for notifications
   is **not** yet implemented).
3. CDC replication to ES for free-text search across notifications is
   out of scope for v1; revisit if support tickets need cross-library
   search by title/body.

## 9. Change log

| Date | Change | Author |
|---|---|---|
| 2026-05-06 | Initial draft (ADR_REVIEW §11.4 follow-up). | backend |
