#!/usr/bin/env bash
# Stash, list, or unstash Novel OS projects via stash_project.py.
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
APP="$INSTALL_ROOT/app"
VENV="$INSTALL_ROOT/venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Python venv missing at $VENV" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
exec python "$APP/scripts/stash_project.py" "$@"
