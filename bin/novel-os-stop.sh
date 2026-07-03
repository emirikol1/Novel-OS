#!/usr/bin/env bash
# Stop Novel-OS API and web UI processes started by novel-os-launch.sh
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
RUN="$INSTALL_ROOT/run"
LOG="$INSTALL_ROOT/logs"
BACKEND_PID="$RUN/backend.pid"
FRONTEND_PID="$RUN/frontend.pid"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG/launcher.log"
}

stop_pidfile() {
  local pidfile=$1
  local label=$2
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
      log "Stopped $label pid=$pid"
    fi
    rm -f "$pidfile"
  fi
}

kill_port() {
  local port=$1
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  elif command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
    fi
  fi
}

stop_pidfile "$FRONTEND_PID" "frontend"
stop_pidfile "$BACKEND_PID" "backend"
kill_port 5173
kill_port 8000

if command -v notify-send >/dev/null 2>&1; then
  notify-send "Novel-OS" "Stopped API and web UI" 2>/dev/null || true
fi
log "Stop complete"
