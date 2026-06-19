#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BEGIN_MARKER="<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
END_MARKER="<!-- END AGENT_PROJECT_MEMORY_RULES -->"

usage() {
  cat <<'EOF'
Usage: bash installers/uninstall.sh [options]

Options:
  --agent <codex|claude|gemini>  Agent type used for rules-file detection.
  --target <path>                Agent config directory. Defaults to ~/.codex.
  --rules-file <path>            Remove managed block from this file.
  --remove-memory                Also remove project_memory after backup.
  --dry-run                      Print planned changes without writing files.
  --yes                          Skip confirmation prompts.
  --help                         Show this help.
EOF
}

say() { printf '%s\n' "$*"; }
action() { if [[ "$1" == "1" ]]; then shift; printf '[dry-run] %s\n' "$*"; else shift; printf '%s\n' "$*"; fi; }
timestamp() { date +%Y%m%d%H%M%S; }
backup_path() { printf '%s.backup.%s' "$1" "$(timestamp)"; }

backup_item() {
  local path="$1" dry_run="$2"
  if [[ ! -e "$path" ]]; then return 0; fi
  local backup
  backup="$(backup_path "$path")"
  action "$dry_run" "backup $path -> $backup"
  if [[ "$dry_run" != "1" ]]; then
    cp -R "$path" "$backup"
  fi
}

detect_rules_file() {
  local target="$1" agent="$2" explicit="$3"
  if [[ -n "$explicit" ]]; then printf '%s\n' "$explicit"; return 0; fi
  local candidates=()
  case "$agent" in
    codex) candidates=("$target/AGENTS.md" "$target/CODEX.md" "$target/instructions.md") ;;
    claude) candidates=("$target/CLAUDE.md" "$target/instructions.md" "$target/AGENTS.md") ;;
    gemini) candidates=("$target/GEMINI.md" "$target/AGENTS.md" "$target/instructions.md") ;;
    *) candidates=("$target/AGENTS.md" "$target/instructions.md") ;;
  esac
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then printf '%s\n' "$candidate"; return 0; fi
  done
  return 1
}

remove_block() {
  local file="$1" dry_run="$2"
  if [[ ! -f "$file" ]]; then
    action "$dry_run" "rules file not found: $file"
    return 0
  fi
  if ! grep -Fq "$BEGIN_MARKER" "$file"; then
    action "$dry_run" "managed block not present in $file"
    return 0
  fi
  backup_item "$file" "$dry_run"
  action "$dry_run" "remove managed rule block from $file"
  if [[ "$dry_run" == "1" ]]; then return 0; fi
  local output
  output="$(mktemp)"
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { in_block = 1; next }
    $0 == end { in_block = 0; next }
    !in_block { print }
  ' "$file" > "$output"
  mv "$output" "$file"
}

agent="codex"
target="${HOME}/.codex"
rules_file=""
remove_memory=0
dry_run=0
yes=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) agent="${2:-}"; shift 2 ;;
    --target) target="${2:-}"; shift 2 ;;
    --rules-file) rules_file="${2:-}"; shift 2 ;;
    --remove-memory) remove_memory=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    --yes) yes=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) say "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say "Agent Project Memory uninstall"
say "Agent: $agent"
say "Target: $target"
if [[ "$dry_run" == "1" ]]; then say "Mode: dry-run"; fi

if [[ "$dry_run" != "1" && "$yes" != "1" ]]; then
  printf 'Uninstall managed Agent Project Memory rules from %s? [y/N] ' "$target"
  reply=""
  read -r reply || true
  case "$reply" in y|Y|yes|YES) ;; *) say "Cancelled."; exit 1 ;; esac
fi

if detected="$(detect_rules_file "$target" "$agent" "$rules_file")"; then
  remove_block "$detected" "$dry_run"
else
  fallback="$target/PROJECT_MEMORY_RULES_TO_ADD.md"
  if [[ -f "$fallback" ]]; then
    backup_item "$fallback" "$dry_run"
    action "$dry_run" "remove fallback rules file $fallback"
    if [[ "$dry_run" != "1" ]]; then rm -f "$fallback"; fi
  else
    say "No rules file found; nothing to remove from rules."
  fi
fi

if [[ "$remove_memory" == "1" ]]; then
  memory_dir="$target/project_memory"
  if [[ -d "$memory_dir" ]]; then
    backup_item "$memory_dir" "$dry_run"
    action "$dry_run" "remove memory directory $memory_dir"
    if [[ "$dry_run" != "1" ]]; then rm -rf "$memory_dir"; fi
  else
    say "Memory directory not found: $memory_dir"
  fi
else
  say "project_memory data was kept. Use --remove-memory to remove it explicitly."
fi
