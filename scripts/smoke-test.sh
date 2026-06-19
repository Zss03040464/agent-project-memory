#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash -n installers/install-common.sh
bash -n installers/install-codex.sh
bash -n installers/install-claude.sh
bash -n installers/install-gemini.sh
bash -n installers/uninstall.sh

python3 tests/test_installers.py
python3 scripts/privacy_scan.py

echo "Smoke test passed."
