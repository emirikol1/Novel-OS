#!/usr/bin/env bash
# Restart Novel OS API + web UI (no browser). Used by the in-app Restart button.
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
BIN="$INSTALL_ROOT/bin"
APP="$INSTALL_ROOT/app"
VENV="$INSTALL_ROOT/venv"
LOG="$INSTALL_ROOT/logs"
RUN="$INSTALL_ROOT/run"
PROJECTS="$INSTALL_ROOT/projects"

export NOVEL_OS_HOME="$INSTALL_ROOT"
export NOVEL_OS_PROJECTS_DIR="$PROJECTS"
export PATH="$VENV/bin:$PATH"

if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
fi

if [[ -f "$APP/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP/.env"
  set +a
fi

"$BIN/novel-os-stop.sh" >/dev/null 2>&1 || true
sleep 1

(
  cd "$APP"
  export LMSTUDIO_API_KEY NOVEL_OS_API_KEY NOVEL_OS_LLM_PROVIDER NOVEL_OS_MODEL \
    NOVEL_OS_BASE_URL NOVEL_OS_MAX_TOKENS NOVEL_OS_PROJECTS_DIR
  exec uvicorn api.main:app --host 127.0.0.1 --port 8000
) >>"$LOG/backend.log" 2>&1 &
echo $! >"$RUN/backend.pid"

(
  cd "$APP/web"
  exec npm run dev -- --host 127.0.0.1 --port 5173
) >>"$LOG/frontend.log" 2>&1 &
echo $! >"$RUN/frontend.pid"

printf '[%s] Restart complete (backend pid=%s frontend pid=%s)\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" "$(cat "$RUN/backend.pid")" "$(cat "$RUN/frontend.pid")" \
  >>"$LOG/launcher.log"

wait_for_http() {
  local url=$1
  local label=$2
  local tries=${3:-90}
  local i=0
  while (( i < tries )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      printf '[%s] %s ready at %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$label" "$url" >>"$LOG/launcher.log"
      return 0
    fi
    sleep 1
    ((i++)) || true
  done
  printf '[%s] WARN: %s not ready at %s after %ss\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$label" "$url" "$tries" >>"$LOG/launcher.log"
  return 1
}

wait_for_http "http://127.0.0.1:8000/api/health" "API" 90 || true
wait_for_http "http://127.0.0.1:5173" "UI" 90 || true
