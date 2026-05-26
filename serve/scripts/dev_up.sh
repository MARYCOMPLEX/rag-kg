#!/usr/bin/env bash
# 一键启动 RAG-KG Copilot 本地开发环境
#
# 用法:
#   scripts/dev_up.sh              # 启动全部 (跳过依赖安装)
#   scripts/dev_up.sh --install    # 强制重新装依赖
#   scripts/dev_up.sh --no-web     # 不起前端
#   scripts/dev_up.sh --no-worker  # 不起 worker
#   scripts/dev_up.sh down         # 停止全部
#
# 默认不装依赖。uv 和 pnpm 都是增量幂等的——锁文件没变就秒过，
# 真有变化时再加 --install。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/.dev-logs"
PID_DIR="$ROOT/.dev-pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

API_PID="$PID_DIR/api.pid"
WORKER_PID="$PID_DIR/worker.pid"
WEB_PID="$PID_DIR/web.pid"

color()  { printf "\033[1;36m[dev]\033[0m %s\n" "$*"; }
warn()   { printf "\033[1;33m[dev]\033[0m %s\n" "$*"; }
fail()   { printf "\033[1;31m[dev]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------- shutdown ----------
stop_pid() {
  local pidfile="$1" name="$2"
  if [[ -f "$pidfile" ]]; then
    local pid; pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      color "stopping $name (pid=$pid)"
      kill "$pid" 2>/dev/null || true
      # 给 5 秒优雅退出
      for _ in {1..10}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
  fi
}

cmd_down() {
  stop_pid "$API_PID"    "api"
  stop_pid "$WORKER_PID" "worker"
  stop_pid "$WEB_PID"    "web"
  color "stopping docker data layer"
  docker compose -f infra/docker-compose.yml --profile full down
  color "down"
}

if [[ "${1:-}" == "down" ]]; then
  cmd_down
  exit 0
fi

# ---------- args ----------
DO_INSTALL=0
RUN_WEB=1
RUN_WORKER=1
for arg in "$@"; do
  case "$arg" in
    --install)    DO_INSTALL=1 ;;
    --no-web)     RUN_WEB=0 ;;
    --no-worker)  RUN_WORKER=0 ;;
    *) fail "unknown arg: $arg" ;;
  esac
done

# ---------- preflight ----------
command -v uv     >/dev/null || fail "uv not installed (https://docs.astral.sh/uv/)"
command -v docker >/dev/null || fail "docker not installed"
[[ -f .env ]] || fail ".env missing — copy from .env.example first"

# ---------- install (optional) ----------
if [[ $DO_INSTALL -eq 1 ]]; then
  color "uv sync"
  uv sync
  if [[ $RUN_WEB -eq 1 ]]; then
    command -v pnpm >/dev/null || fail "pnpm not installed"
    color "pnpm install (apps/web)"
    (cd apps/web && pnpm install)
  fi
else
  [[ -d .venv ]] || warn ".venv missing — run with --install"
  if [[ $RUN_WEB -eq 1 && ! -d apps/web/node_modules ]]; then
    warn "apps/web/node_modules missing — run with --install"
  fi
fi

# ---------- docker data layer ----------
color "starting docker data layer"
docker compose -f infra/docker-compose.yml up -d

# ---------- api ----------
if [[ -f "$API_PID" ]] && kill -0 "$(cat "$API_PID")" 2>/dev/null; then
  warn "api already running (pid=$(cat "$API_PID")) — skipping"
else
  color "starting api  → $LOG_DIR/api.log"
  nohup uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 \
    >"$LOG_DIR/api.log" 2>&1 &
  echo $! > "$API_PID"
fi

# 等 healthz
color "waiting for http://localhost:8000/healthz"
for i in {1..40}; do
  if curl -sf http://localhost:8000/healthz >/dev/null 2>&1; then
    color "api ready"
    break
  fi
  sleep 1
  [[ $i -eq 40 ]] && warn "api still not healthy — check $LOG_DIR/api.log"
done

# ---------- worker ----------
if [[ $RUN_WORKER -eq 1 ]]; then
  if [[ -f "$WORKER_PID" ]] && kill -0 "$(cat "$WORKER_PID")" 2>/dev/null; then
    warn "worker already running (pid=$(cat "$WORKER_PID")) — skipping"
  else
    color "starting worker  → $LOG_DIR/worker.log"
    nohup uv run arq apps.worker.main.WorkerSettings \
      >"$LOG_DIR/worker.log" 2>&1 &
    echo $! > "$WORKER_PID"
  fi
fi

# ---------- web ----------
if [[ $RUN_WEB -eq 1 ]]; then
  command -v pnpm >/dev/null || fail "pnpm not installed"
  if [[ -f "$WEB_PID" ]] && kill -0 "$(cat "$WEB_PID")" 2>/dev/null; then
    warn "web already running (pid=$(cat "$WEB_PID")) — skipping"
  else
    color "starting web   → $LOG_DIR/web.log"
    (cd apps/web && nohup pnpm dev >"$LOG_DIR/web.log" 2>&1 &
     echo $! > "$WEB_PID")
  fi
fi

# ---------- summary ----------
cat <<EOF

\033[1;32m===== ready =====\033[0m
  api    → http://localhost:8000   (healthz: /healthz)
  web    → http://localhost:5173
  logs   → $LOG_DIR/{api,worker,web}.log
  pids   → $PID_DIR/

stop everything:
  scripts/dev_up.sh down
EOF
