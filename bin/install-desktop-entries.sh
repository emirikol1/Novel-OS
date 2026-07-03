#!/usr/bin/env bash
# Install Novel-OS launch/stop entries to the application menu (~/.local/share/applications).
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
DESKTOP_SRC="$INSTALL_ROOT/desktop"
APPS_DIR="$HOME/.local/share/applications"

if [[ ! -d "$DESKTOP_SRC" ]]; then
  echo "Error: desktop templates not found at $DESKTOP_SRC" >&2
  exit 1
fi

mkdir -p "$APPS_DIR"

for src in "$DESKTOP_SRC"/*.desktop; do
  [[ -f "$src" ]] || continue
  dest="$APPS_DIR/$(basename "$src")"
  sed "s|@NOVEL_OS_HOME@|$INSTALL_ROOT|g" "$src" >"$dest"
  chmod 644 "$dest"
  echo "Installed $dest"
done

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "Done. Launch and Stop Novel-OS should appear in your application menu."
