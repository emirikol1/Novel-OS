#!/usr/bin/env bash
# Start Novel-OS API + web UI, then open the dashboard in your browser.
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
APP="$INSTALL_ROOT/app"
VENV="$INSTALL_ROOT/venv"
LOG="$INSTALL_ROOT/logs"
RUN="$INSTALL_ROOT/run"
PROJECTS="$INSTALL_ROOT/projects"
STASHED="$INSTALL_ROOT/stashed"
BACKEND_PID="$RUN/backend.pid"
FRONTEND_PID="$RUN/frontend.pid"
LAUNCHER_LOG="$LOG/launcher.log"
UI_URL="http://127.0.0.1:5173"

# Desktop menu launchers use a minimal PATH — ensure node/npm from nvm are available.
if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
fi
if ! command -v npm >/dev/null 2>&1; then
  for node_bin in "$HOME"/.nvm/versions/node/*/bin; do
    if [[ -x "$node_bin/npm" ]]; then
      PATH="$node_bin:$PATH"
      break
    fi
  done
fi
export PATH="$VENV/bin:$PATH"

mkdir -p "$LOG" "$RUN" "$PROJECTS" "$STASHED"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LAUNCHER_LOG"
}

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Novel-OS" "$1" 2>/dev/null || true
  fi
}

fail() {
  log "ERROR: $*"
  notify "Failed to start: $*"
  exit 1
}

if [[ ! -d "$APP" ]]; then
  fail "App not found at $APP — run the install step first."
fi
if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  fail "Python venv missing at $VENV — run: pip install -r $APP/requirements.txt"
fi
if [[ ! -d "$APP/web/node_modules" ]]; then
  fail "Web dependencies missing — run: cd $APP/web && npm install"
fi
if ! command -v npm >/dev/null 2>&1; then
  fail "npm not found in PATH — install Node.js or nvm"
fi

export NOVEL_OS_PROJECTS_DIR="$PROJECTS"

if [[ -f "$APP/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP/.env"
  set +a
fi

is_alive() {
  local pidfile=$1
  [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

wait_for_http() {
  local url=$1
  local label=$2
  local tries=${3:-90}
  local i=0
  while (( i < tries )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$label ready at $url"
      return 0
    fi
    sleep 1
    ((i++)) || true
  done
  return 1
}

port_in_use() {
  local port=$1
  ss -ltn 2>/dev/null | grep -q ":${port} " || \
    lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1
}

start_backend() {
  if is_alive "$BACKEND_PID" || port_in_use 8000; then
    log "Backend already running"
    return 0
  fi
  rm -f "$BACKEND_PID"
  (
    cd "$APP"
    # Pass LM Studio credentials into the API worker (agent jobs use LLMClient).
    export LMSTUDIO_API_KEY NOVEL_OS_API_KEY NOVEL_OS_LLM_PROVIDER NOVEL_OS_MODEL \
      NOVEL_OS_BASE_URL NOVEL_OS_MAX_TOKENS NOVEL_OS_PROJECTS_DIR
    exec uvicorn api.main:app --host 127.0.0.1 --port 8000
  ) >>"$LOG/backend.log" 2>&1 &
  echo $! >"$BACKEND_PID"
  log "Started backend pid=$(cat "$BACKEND_PID")"
}

start_frontend() {
  if is_alive "$FRONTEND_PID" || port_in_use 5173; then
    log "Frontend already running"
    return 0
  fi
  rm -f "$FRONTEND_PID"
  (
    cd "$APP/web"
    exec npm run dev -- --host 127.0.0.1 --port 5173
  ) >>"$LOG/frontend.log" 2>&1 &
  echo $! >"$FRONTEND_PID"
  log "Started frontend pid=$(cat "$FRONTEND_PID")"
}

log "Launch requested (model=${NOVEL_OS_MODEL:-unset}, max_tokens=${NOVEL_OS_MAX_TOKENS:-8192})"

check_lmstudio() {
  local base="${NOVEL_OS_BASE_URL:-http://127.0.0.1:1234/v1}"
  base="${base%/}"
  local key="${LMSTUDIO_API_KEY:-${NOVEL_OS_API_KEY:-}}"
  local curl_args=(-sS --connect-timeout 3 --max-time 10)
  if [[ -n "$key" ]]; then
    curl_args+=(-H "Authorization: Bearer ${key}")
  fi

  local http_code
  http_code=$(curl "${curl_args[@]}" -o /dev/null -w "%{http_code}" "${base}/models" 2>/dev/null || echo "000")

  case "$http_code" in
    200)
      ;;
    401)
      log "WARN: LM Studio at ${base} requires a valid API token (HTTP 401)"
      notify "LM Studio API key missing or invalid — check .env"
      return 1
      ;;
    000)
      log "WARN: LM Studio not reachable at ${base} — is Local Server running?"
      notify "LM Studio not reachable — start Local Server before writing"
      return 1
      ;;
    *)
      log "WARN: LM Studio at ${base} returned HTTP ${http_code}"
      notify "LM Studio check failed (HTTP ${http_code})"
      return 1
      ;;
  esac

  local models
  models=$(curl "${curl_args[@]}" "${base}/models" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ids = [m.get('id','') for m in data.get('data', [])]
print('\n'.join(ids))
" 2>/dev/null || true)
  if [[ -n "$models" ]]; then
    log "LM Studio models: $(echo "$models" | tr '\n' ', ' | sed 's/, $//')"
    if [[ -n "${NOVEL_OS_MODEL:-}" ]] && ! echo "$models" | grep -Fxq "$NOVEL_OS_MODEL"; then
      log "WARN: configured NOVEL_OS_MODEL=$NOVEL_OS_MODEL not in loaded models list"
      notify "Configured model not loaded in LM Studio — check .env"
    else
      log "LM Studio OK — using ${NOVEL_OS_MODEL:-loaded model}"
    fi
  fi
  return 0
}

check_lmstudio || true
start_backend
start_frontend

if ! wait_for_http "http://127.0.0.1:8000/api/health" "API" 90; then
  fail "API did not become ready — see $LOG/backend.log"
fi
if ! wait_for_http "$UI_URL" "UI" 90; then
  fail "UI did not become ready — see $LOG/frontend.log"
fi

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$UI_URL" >/dev/null 2>&1 || true
elif command -v gio >/dev/null 2>&1; then
  gio open "$UI_URL" >/dev/null 2>&1 || true
fi

notify "Dashboard running at $UI_URL"
log "Launch complete — $UI_URL"
