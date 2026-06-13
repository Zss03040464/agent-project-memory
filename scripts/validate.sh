#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

required=(
  "README.md"
  ".codex/AGENTS.md"
  ".codex/project_memory/INDEX.md"
  ".codex/project_memory/templates/RECORD_TEMPLATE.md"
  ".codex/project_memory/templates/SESSION_TEMPLATE.md"
)

for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing required file: $path" >&2
    exit 1
  fi
done

if grep -RInE '(sk-[A-Za-z0-9_-]{12,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|password\s*=|token\s*=)' . \
  --exclude-dir=.git \
  --exclude='validate.sh'; then
  echo "potential secret-like content found; review before publishing" >&2
  exit 1
fi

echo "agent-project-memory validation passed"
