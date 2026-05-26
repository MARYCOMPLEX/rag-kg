# Observability Stack

Self-hosted observability for the RAG-KG Copilot:

- **Prometheus** — metrics scraping + alerting rules (port `9090`)
- **Tempo** — distributed traces via OTLP gRPC (port `4317`) / HTTP (port `4318`)
- **Loki** — log aggregation (port `3100`)
- **Grafana** — dashboards and exploration (port `3001`)

The stack is opt-in via the `observability` Compose profile so it never starts
with the default `make up`.

## Start the stack

```bash
docker compose \
  -f infra/docker-compose.yml \
  -f infra/observability/docker-compose.observability.yml \
  --profile observability up -d
```

A convenience target can be added to the project Makefile:

```makefile
up-obs:
	docker compose \
		-f infra/docker-compose.yml \
		-f infra/observability/docker-compose.observability.yml \
		--profile observability up -d
```

## Stop the stack

```bash
docker compose \
  -f infra/docker-compose.yml \
  -f infra/observability/docker-compose.observability.yml \
  --profile observability down
```

## First login

- URL: <http://localhost:3001>
- User: `admin`
- Password: `admin` (Grafana will force a password change on first login)

Datasources (Prometheus, Tempo, Loki) and dashboards are auto-provisioned on
boot via the files under `infra/grafana/provisioning/`.

## Bundled dashboards

| Dashboard | UID | Purpose |
|-----------|------|---------|
| RAG Quality | `rag-quality` | Eval pass rate, citation F1, composite score by suite. Variables: `library_id`, `suite`. |
| RAG Performance | `rag-performance` | P95 retrieval latency, retrieval hits by source (vector / bm25 / community), LLM tokens/min, LLM USD/hour. |
| RAG Cost | `rag-cost` | LLM cost by model (table), embedding cost by model (table), cost per library over the last 7 days. |

## Adding a new dashboard

1. Build the dashboard in Grafana UI, then **Share → Export → Save to file**
   (toggle "Export for sharing externally" off to keep datasource UIDs).
2. Drop the JSON into `infra/grafana/dashboards/`.
3. Restart Grafana so the provisioner picks it up:

   ```bash
   docker compose \
     -f infra/docker-compose.yml \
     -f infra/observability/docker-compose.observability.yml \
     restart grafana
   ```

Alternatively, the provider config polls every 30s, so the dashboard will
appear without a restart in most cases.

## Alert rules

Prometheus rules live in `infra/observability/alerting/`. Current alerts:

| Alert | Severity | Trigger |
|-------|----------|---------|
| `rag_eval_pass_rate_drop` | warning | Pass rate over 24h drops >10pp vs prior 24h. |
| `rag_llm_p95_latency_high` | warning | LLM call p95 > 60s for 10m. |
| `rag_llm_error_rate_high` | critical | LLM error rate > 10% over 5m. |
| `rag_embedding_cache_miss_high` | info | Embedding cache miss rate > 50% for 1h. |

To wire alerts to a real notifier (Slack, PagerDuty, email), deploy
Alertmanager and update the `alerting:` block in
`infra/observability/prometheus/prometheus.yml`.

## Metric naming convention

All RAG metrics are prefixed `rag_`. Counters end in `_total`, histograms in
`_seconds` / `_bucket`, and money in `_usd_total`. Common labels:
`library_id`, `suite`, `model`, `source`, `kind`.

## Notes

- Default Grafana credentials must be rotated before any non-local deploy.
- Prometheus retention defaults to 30d, Loki / Tempo to 7d. Tune in the
  respective config files under `infra/observability/`.
- The `apps/api` scrape target uses `host.docker.internal:8000`, which works
  on Docker Desktop (macOS / Windows). For Linux, add
  `extra_hosts: ["host.docker.internal:host-gateway"]` to the prometheus
  service or scrape via the Compose network.
- Langfuse (LLM trace UI) is deployed separately and is **not** part of this
  stack.
