#!/usr/bin/env bash
# run.sh — one-command launcher for the 王凡周报生成器 dev environment.
#
# Usage:
#   bash run.sh           start backend (:8000) + frontend (:5173), block until Ctrl-C
#   bash run.sh --detached start in background, return immediately (use --logs / --stop)
#   bash run.sh --stop    kill any running wfreport processes (backend + frontend + vite)
#   bash run.sh --check   print environment status, don't start
#   bash run.sh --test [dir]  run pytest for the given subdir (default: tests/core)
#   bash run.sh --logs    tail backend + frontend logs
#   bash run.sh --install install backend + frontend deps
#   bash run.sh --open    also open the browser when ready
#
# Logs (always written):
#   /tmp/wfreport-backend.log
#   /tmp/wfreport-frontend.log

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV=".venv"
LOG_BE="/tmp/wfreport-backend.log"
LOG_FE="/tmp/wfreport-frontend.log"

# ---- colour helpers (no-op if NO_COLOR / not a tty) ----
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\e[0m'
  C_DIM=$'\e[2m'
  C_RED=$'\e[31m'
  C_GREEN=$'\e[32m'
  C_YELLOW=$'\e[33m'
  C_BLUE=$'\e[34m'
  C_BOLD=$'\e[1m'
else
  C_RESET= C_DIM= C_RED= C_GREEN= C_YELLOW= C_BLUE= C_BOLD=
fi

say()    { printf "%s\n" "$*"; }
ok()     { printf "%s✓%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn()   { printf "%s!%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
err()    { printf "%s✗%s %s\n" "$C_RED"   "$C_RESET" "$*" >&2; }
header() { printf "\n%s%s%s\n" "$C_BOLD$C_BLUE" "$*" "$C_RESET"; }

# ---- pre-flight helpers ----
# Returns the first executable name that exists in PATH. Pass one or more
# candidate names; the function does NOT consume the first arg as a label.
first_exe() {
  for c in "$@"; do
    if command -v "$c" >/dev/null 2>&1; then
      printf '%s' "$c"; return 0
    fi
  done
  printf '%s' ""
}

# ---- arg parsing ----
MODE="start"
DETACHED=0
OPEN_BROWSER=0
TEST_DIR=""
INSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stop)      MODE="stop" ;;
    --check)     MODE="check" ;;
    --logs)      MODE="logs" ;;
    --test)      MODE="test"; shift; TEST_DIR="${1:-tests/core}" ;;
    --install)   MODE="install"; INSTALL=1 ;;
    --detached)  DETACHED=1 ;;
    --open)      OPEN_BROWSER=1 ;;
    -h|--help)
      sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# *//'
      exit 0 ;;
    *)
      err "unknown flag: $1"; exit 64 ;;
  esac
  shift
done

# ===========================================================================
# pre-flight: find uv, node
# ===========================================================================
UV_BIN="$(first_exe uv)"
NODE_BIN="$(first_exe node nodejs)"
NPM_BIN="$(first_exe npm)"

require_uv() {
  if [[ -z "$UV_BIN" ]]; then
    err "uv not found in PATH — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
}

# ---- OS helpers ----
case "$(uname -s 2>/dev/null || echo unknown)" in
  Linux*|Darwin*) OPEN_CMD="open" ;;        # macOS
  *)               OPEN_CMD="xdg-open" ;;    # fall back to xdg-open on Linux
esac

# ===========================================================================
# mode: --stop  ----------------------------------------------------------
# ===========================================================================
if [[ "$MODE" == "stop" ]]; then
  header "Stopping 王凡周报生成器 services"
  # kill anything listening on backend/frontend ports, plus named processes
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    pids="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
    [[ -z "$pids" ]] && pids="$(lsof -ti :"$port" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      say "${C_DIM}port $port: killing pids $pids${C_RESET}"
      kill -TERM $pids 2>/dev/null || true
    fi
  done
  for pat in "uvicorn.*backend.app.main" "vite" "node.*vite"; do
    pkill -f "$pat" 2>/dev/null || true
  done
  sleep 0.5
  for pat in "uvicorn.*backend.app.main" "vite"; do
    pkill -KILL -f "$pat" 2>/dev/null || true
  done
  ok "stopped"
  exit 0
fi

# ===========================================================================
# mode: --logs  -----------------------------------------------------------
# ===========================================================================
if [[ "$MODE" == "logs" ]]; then
  if [[ ! -f "$LOG_BE" && ! -f "$LOG_FE" ]]; then
    err "no logs found at $LOG_BE / $LOG_FE"; exit 1
  fi
  say "${C_DIM}streaming logs (Ctrl-C to exit)${C_RESET}"
  exec tail -n 50 -F "$LOG_BE" "$LOG_FE"
fi

# ===========================================================================
# shared print: environment
# ===========================================================================
print_env() {
  header "Environment"
  ok  "repo:        $REPO_ROOT"
  [[ -n "$UV_BIN"   ]] && ok  "uv:          $UV_BIN ($("$UV_BIN" --version | awk '{print $2}'))" || warn "uv:          missing"
  [[ -n "$NODE_BIN" ]] && ok  "node:        $NODE_BIN ($(node -v 2>/dev/null))" || warn "node:        missing"
  [[ -n "$NPM_BIN"  ]] && ok  "npm:         $NPM_BIN"  || warn "npm:         missing"
  if [[ -d "$VENV" ]]; then
    ok "python:      $("$VENV/bin/python" -c 'import platform;print(platform.python_version())') (.venv, managed by uv)"
  fi
}

print_env

# ===========================================================================
# mode: --check  ----------------------------------------------------------
# ===========================================================================
if [[ "$MODE" == "check" ]]; then
  header "Backend deps"
  if [[ ! -d "$VENV" ]]; then warn ".venv missing — will be created on first run"
  else ok ".venv present (Python $($VENV/bin/python -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'))"; fi
  if [[ -d "$VENV" ]]; then
    if "$VENV/bin/python" -c "import fastapi, pandas, plotly, kaleido, xlsxwriter, pptx, httpx, yaml, dotenv, openpyxl" 2>/dev/null; then
      ok "backend imports OK"
    else
      warn "backend imports missing — run: bash run.sh --install"
    fi
  fi

  header "Frontend deps"
  if [[ ! -d "frontend/node_modules" ]]; then warn "node_modules missing — run: bash run.sh --install"
  else ok "node_modules present"; fi

  if [[ -f ".env" ]]; then
    ok ".env present"
    for k in MINIMAX_API_KEY DEEPSEEK_API_KEY KIMI_API_KEY; do
      if grep -q "^${k}=" .env && [[ -n "$(grep "^${k}=" .env | cut -d= -f2-)" ]]; then
        ok "  $k set"
      else
        warn "  $k empty (AI calls for $k will fall back to placeholder)"
      fi
    done
  else
    warn ".env missing — copy from .env.example"
  fi
  exit 0
fi

# ===========================================================================
# mode: --install  --------------------------------------------------------
# ===========================================================================
ensure_backend_deps() {
  require_uv
  if [[ ! -d "$VENV" ]]; then
    header "Syncing backend deps (uv sync)"
    "$UV_BIN" sync
    ok "venv created at $VENV"
  else
    "$UV_BIN" sync --quiet
  fi
}
ensure_frontend_deps() {
  if [[ ! -d "frontend/node_modules" ]]; then
    header "Installing frontend deps"
    ( cd frontend && "$NPM_BIN" install --no-audit --no-fund --loglevel=error )
    ok "frontend deps installed"
  fi
}

if [[ "$MODE" == "install" || "$INSTALL" == 1 ]]; then
  ensure_backend_deps
  ensure_frontend_deps
  ok "all deps ready"
  exit 0
fi

# ===========================================================================
# mode: --test  -----------------------------------------------------------
# ===========================================================================
if [[ "$MODE" == "test" ]]; then
  ensure_backend_deps
  header "pytest $TEST_DIR"
  exec "$VENV/bin/python" -m pytest "$TEST_DIR" -v
fi

# ===========================================================================
# mode: start  ------------------------------------------------------------
# ===========================================================================

# 1) ensure deps
ensure_backend_deps
ensure_frontend_deps

# 2) free the ports if zombies are squatting
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  [[ -z "$pids" ]] && pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    warn "port $port in use by pid(s) $pids — killing"
    kill -TERM $pids 2>/dev/null || true
    sleep 0.4
    kill -KILL $pids 2>/dev/null || true
  fi
done

# 3) load .env if present
if [[ -f ".env" ]]; then
  set -a; . ./.env; set +a
  ok "loaded .env"
fi

# 4) launch backend in its own process group (so Ctrl-C kills children)
header "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT"
: > "$LOG_BE"
setsid "$VENV/bin/python" -m uvicorn backend.app.main:app \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" --no-access-log \
    > "$LOG_BE" 2>&1 &
PIDS+=($!)
BE_PID=$!
ok "backend pid=$BE_PID  logs=$LOG_BE"

# 5) launch frontend
header "Starting frontend on http://localhost:$FRONTEND_PORT"
: > "$LOG_FE"
( cd frontend && setsid "$NPM_BIN" run dev -- --port "$FRONTEND_PORT" --strictPort \
    > "$LOG_FE" 2>&1 & echo $! > /tmp/wfreport-fe.pid )
FE_PID="$(cat /tmp/wfreport-fe.pid 2>/dev/null || echo "")"
PIDS+=("$FE_PID")
ok "frontend pid=$FE_PID  logs=$LOG_FE"

# 6) wait for both to respond
header "Waiting for services"
for i in {1..40}; do
  be_ok=0; fe_ok=0
  if curl -fsS --max-time 1 "http://$BACKEND_HOST:$BACKEND_PORT/api/ai/providers" >/dev/null 2>&1; then be_ok=1; fi
  if curl -fsS --max-time 1 "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then fe_ok=1; fi
  if [[ $be_ok == 1 && $fe_ok == 1 ]]; then break; fi
  sleep 0.5
done

if [[ $be_ok == 1 ]]; then ok "backend  ready  http://$BACKEND_HOST:$BACKEND_PORT"
else warn "backend  not ready yet  (check $LOG_BE)"; fi
if [[ $fe_ok == 1 ]]; then ok "frontend ready  http://localhost:$FRONTEND_PORT"
else warn "frontend not ready yet  (check $LOG_FE)"; fi

header "Ready"
cat <<EOF

  ${C_BOLD}Web UI:${C_RESET}      http://localhost:$FRONTEND_PORT
  ${C_BOLD}API:${C_RESET}        http://$BACKEND_HOST:$BACKEND_PORT
  ${C_BOLD}API docs:${C_RESET}   http://$BACKEND_HOST:$BACKEND_PORT/docs

  ${C_DIM}logs:${C_RESET}       bash run.sh --logs
  ${C_DIM}stop:${C_RESET}       bash run.sh --stop

EOF

# 7) optional: open browser
if [[ $OPEN_BROWSER == 1 ]]; then
  if command -v "$OPEN_CMD" >/dev/null 2>&1; then
    ( "$OPEN_CMD" "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1 & ) || true
  fi
fi

# 8) block (or detach)
if [[ $DETACHED == 1 ]]; then
  ok "detached — services running in background. use 'bash run.sh --stop' to stop."
  exit 0
fi

# tail logs while waiting for Ctrl-C
trap 'cleanup INT' INT
say "${C_DIM}streaming logs (Ctrl-C to stop and exit)${C_RESET}"
tail --pid="${PIDS[0]}" -n +1 -F "$LOG_BE" "$LOG_FE" 2>/dev/null &
TAIL_PID=$!
wait "${PIDS[0]}" 2>/dev/null || true
kill "$TAIL_PID" 2>/dev/null || true
cleanup TERM
