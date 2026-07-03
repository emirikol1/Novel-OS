#!/usr/bin/env bash
# Create a Novel-OS *install* backup: code, config, launchers — no novel/project data.
# User manuscripts restore separately via in-app project backups or projects/ copy.
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
APP="$INSTALL_ROOT/app"
STAMP="$(date '+%Y-%m-%d_%H%M%S')"
DEFAULT_OUT="$HOME/Documents/backups"
OUT_DIR="${1:-$DEFAULT_OUT}"
ARCHIVE="$OUT_DIR/novel-os-mint-restore_${STAMP}.tar.gz"
STAGING="$(mktemp -d)"
BUNDLE="$STAGING/novel-os-mint-restore"

cleanup() { rm -rf "$STAGING"; }
trap cleanup EXIT

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

mkdir -p "$OUT_DIR" "$BUNDLE/install" "$BUNDLE/desktop" "$BUNDLE/cursor/skills" "$BUNDLE/patches"

log "Staging install tree (code only, no user data)…"

# --- app source: full tree minus regenerable runtime + user DB ---
rsync -a \
  --exclude='web/node_modules/' \
  --exclude='web/dist/' \
  --exclude='**/__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='novel_os.db' \
  --exclude='novel_os*.db' \
  --exclude='outputs/' \
  --exclude='*.pyc' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  "$APP/" "$BUNDLE/install/app/"

# --- install infrastructure (not inside app/) ---
for dir in bin config icon desktop; do
  if [[ -d "$INSTALL_ROOT/$dir" ]]; then
    rsync -a "$INSTALL_ROOT/$dir/" "$BUNDLE/install/$dir/"
  fi
done

# --- desktop launchers ---
if [[ -d "$INSTALL_ROOT/desktop" ]]; then
  cp "$INSTALL_ROOT/desktop/"*.desktop "$BUNDLE/desktop/" 2>/dev/null || true
fi
for f in "$HOME/.local/share/applications/novel-os.desktop" \
         "$HOME/.local/share/applications/novel-os-stop.desktop"; do
  [[ -f "$f" ]] && cp "$f" "$BUNDLE/desktop/"
done

# --- Cursor dev skill (optional but part of our workflow) ---
SKILL_SRC="$HOME/.cursor/skills/develop-novelos"
if [[ -d "$SKILL_SRC" ]]; then
  rsync -a "$SKILL_SRC/" "$BUNDLE/cursor/skills/develop-novelos/"
fi

# --- git patch snapshot (belt-and-suspenders alongside full .git) ---
if [[ -d "$APP/.git" ]]; then
  (
    cd "$APP"
    git rev-parse HEAD > "$BUNDLE/patches/HEAD"
    git status -sb > "$BUNDLE/patches/git-status.txt" 2>/dev/null || true
    git diff > "$BUNDLE/patches/uncommitted.patch" 2>/dev/null || true
    git diff --cached >> "$BUNDLE/patches/uncommitted.patch" 2>/dev/null || true
    git ls-files --others --exclude-standard > "$BUNDLE/patches/untracked.txt" 2>/dev/null || true
  )
fi

# --- bundled restore script + docs ---
cat > "$BUNDLE/restore-install.sh" <<'RESTORE'
#!/usr/bin/env bash
# Restore Novel-OS install bundle to a fresh Linux Mint (or similar) user account.
# Does NOT restore novel manuscripts — use in-app project backups for that.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
APP="$INSTALL_ROOT/app"
VENV="$INSTALL_ROOT/venv"

log() { printf '==> %s\n' "$*"; }

if [[ ! -d "$SCRIPT_DIR/install/app" ]]; then
  echo "Error: run this script from inside the extracted novel-os-mint-restore/ folder." >&2
  exit 1
fi

log "Installing to $INSTALL_ROOT"
mkdir -p "$INSTALL_ROOT" "$HOME/.local/share/applications"

rsync -a --delete \
  --exclude='projects/' \
  "$SCRIPT_DIR/install/" "$INSTALL_ROOT/"

# Desktop entries: rewrite install path for this user
for f in "$SCRIPT_DIR/desktop/"*.desktop; do
  [[ -f "$f" ]] || continue
  dest="$HOME/.local/share/applications/$(basename "$f")"
  sed -e "s|@NOVEL_OS_HOME@|$INSTALL_ROOT|g" \
      -e "s|/home/[^/]*/|$HOME/|g" "$f" > "$dest"
  chmod 644 "$dest"
done

if [[ -d "$SCRIPT_DIR/cursor/skills/develop-novelos" ]]; then
  mkdir -p "$HOME/.cursor/skills"
  rsync -a "$SCRIPT_DIR/cursor/skills/develop-novelos/" \
    "$HOME/.cursor/skills/develop-novelos/"
  log "Cursor skill restored to ~/.cursor/skills/develop-novelos/"
fi

log "Creating Python venv…"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip wheel
"$VENV/bin/pip" install -r "$APP/requirements.txt"

log "Installing web dependencies…"
if ! command -v npm >/dev/null 2>&1; then
  if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  fi
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "Warning: npm not found — install Node.js/nvm, then run: cd $APP/web && npm install" >&2
else
  (cd "$APP/web" && npm install)
fi

mkdir -p "$INSTALL_ROOT/projects" "$INSTALL_ROOT/logs" "$INSTALL_ROOT/run"

log "Done. Launch from the Novel-OS menu entry or:"
echo "  $INSTALL_ROOT/bin/novel-os-launch.sh"
echo
echo "To restore novel data separately:"
echo "  • Copy projects/<slug>/ from a data backup, or"
echo "  • Use Project → Backups → Restore in the UI after importing a project package."
RESTORE
chmod +x "$BUNDLE/restore-install.sh"

cat > "$BUNDLE/RESTORE.md" <<'MD'
# Novel-OS mint install restore bundle

This archive contains **application code, configuration, and launchers** for Novel OS.
It does **not** include novel manuscripts, project outputs, or the SQLite database.

## What's included

| Path | Contents |
|------|----------|
| `install/app/` | Python + React source, tests, `.env`, `.git` |
| `install/bin/` | Launch / stop / restart scripts |
| `install/config/` | Global system prefix |
| `install/icon/` | Desktop icon |
| `desktop/` | `.desktop` menu entries |
| `cursor/skills/develop-novelos/` | Cursor agent skill (if present at backup time) |
| `patches/` | Git HEAD, status, diff snapshot |

## Excluded (restore separately)

- `projects/` — novel manuscripts and per-project `outputs/`
- `app/novel_os.db` — install-wide SQLite (included in per-project backup exports)
- `venv/`, `web/node_modules/`, `web/dist/`, logs, PID files

## Fresh Mint restore

1. Install system deps: `python3`, `python3-venv`, `curl`, `git`
2. Install Node.js (recommend [nvm](https://github.com/nvm-sh/nvm))
3. Extract this archive anywhere, e.g. `~/Downloads/novel-os-mint-restore/`
4. Run:

   ```bash
   cd ~/Downloads/novel-os-mint-restore
   ./restore-install.sh
   ```

5. Edit `~/.local/share/novel-os/app/.env` if LM Studio host/model changed
6. Launch **Novel-OS** from the application menu

## Restore novel data

Use in-app **Backups** (Quick save / named backup / restore) on each project,
or copy `projects/<slug>/` from a separate data archive.

After copying `projects/`, restart Novel OS. The app will re-ingest projects into SQLite on access.
MD

# --- manifest ---
{
  echo "created_at=$(date -Iseconds)"
  echo "hostname=$(hostname)"
  echo "user=$USER"
  echo "install_root=$INSTALL_ROOT"
  echo "git_head=$(cat "$BUNDLE/patches/HEAD" 2>/dev/null || echo unknown)"
  echo "archive=$ARCHIVE"
  find "$BUNDLE" -type f | wc -l | awk '{print "file_count="$1}'
  du -sh "$BUNDLE" | awk '{print "staging_size="$1}'
} > "$BUNDLE/MANIFEST.txt"

log "Creating archive: $ARCHIVE"
tar -C "$STAGING" -czf "$ARCHIVE" novel-os-mint-restore

BYTES=$(stat -c%s "$ARCHIVE" 2>/dev/null || stat -f%z "$ARCHIVE")
SHA=$(sha256sum "$ARCHIVE" | awk '{print $1}')
echo "$SHA  $(basename "$ARCHIVE")" > "${ARCHIVE}.sha256"

log "=== Install backup complete ==="
log "Archive:  $ARCHIVE"
log "Size:     $(du -h "$ARCHIVE" | awk '{print $1}')"
log "SHA256:   $SHA"
log "Checksum: ${ARCHIVE}.sha256"
log ""
log "Novel data NOT included. Back up projects separately via in-app Backups."
