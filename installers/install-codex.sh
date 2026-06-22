#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../scripts/manage-install.py" \
  --agent codex --default-target "${HOME}/.codex" --repo-root "$SCRIPT_DIR/.." "$@"
