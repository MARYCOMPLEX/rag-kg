#!/usr/bin/env bash
# Snapshot every library into a timestamped backup folder.
# Designed for cron: keep 30 days of snapshots.
#
# Usage:
#   scripts/snapshot_all.sh [<output-root>]  (default: data/backups)
#   RETENTION_DAYS=7 scripts/snapshot_all.sh
#
# Requires: uv, redis/qdrant/neo4j/opensearch reachable from .env.

set -euo pipefail
cd "$(dirname "$0")/.."

OUT_ROOT="${1:-data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_DIR="${OUT_ROOT}/${TS}"
mkdir -p "${SNAPSHOT_DIR}"

echo "[snapshot] Listing libraries…"
LIBS=$(uv run rkb library list 2>/dev/null | awk 'NR>3 && $1!="" {print $1}' | grep -v '^─' || true)

if [[ -z "${LIBS}" ]]; then
  echo "[snapshot] No libraries to back up."
  exit 0
fi

for lib in ${LIBS}; do
  echo "[snapshot] Exporting ${lib}…"
  uv run rkb library export "${lib}" --out "${SNAPSHOT_DIR}"
done

echo "[snapshot] Pruning archives older than ${RETENTION_DAYS} days from ${OUT_ROOT}…"
find "${OUT_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +

echo "[snapshot] Done → ${SNAPSHOT_DIR}"
