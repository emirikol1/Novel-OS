#!/usr/bin/env bash
# Quick smoke test: Novel-OS -> LM Studio with your configured model.
set -euo pipefail

INSTALL_ROOT="${NOVEL_OS_HOME:-$HOME/.local/share/novel-os}"
APP="$INSTALL_ROOT/app"
VENV="$INSTALL_ROOT/venv"

if [[ -f "$APP/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$APP/.env"
  set +a
fi

export PATH="$VENV/bin:$PATH"
cd "$APP"

echo "Provider:  ${NOVEL_OS_LLM_PROVIDER:-auto}"
echo "Model:     ${NOVEL_OS_MODEL:-auto}"
echo "Base URL:  ${NOVEL_OS_BASE_URL:-http://127.0.0.1:1234/v1}"
echo "Max out:   ${NOVEL_OS_MAX_TOKENS:-8192} tokens (LM Studio context load: 128000)"
echo

python3 - <<'PY'
import os, sys
sys.path.insert(0, "core")
from llm_client import LLMClient, LLMError

try:
    client = LLMClient()
    print(f"Resolved: provider={client.provider} model={client.model} max_tokens={client.max_tokens}")
    text = client.complete(
        "You are a terse assistant.",
        "Reply with exactly: Novel-OS connected.",
    )
    print("Response:", text.strip()[:200])
    print("OK")
except LLMError as e:
    print("FAILED:", e, file=sys.stderr)
    sys.exit(1)
PY
