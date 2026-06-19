#!/usr/bin/env bash
set -euo pipefail

APM_INSTALLER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APM_REPO_ROOT="$(cd "$APM_INSTALLER_DIR/.." && pwd)"
APM_BEGIN="<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
APM_END="<!-- END AGENT_PROJECT_MEMORY_RULES -->"

apm_usage() {
  cat <<'EOF'
Usage: install_project_memory --agent <codex|claude|gemini> --default-target <path> [options]

Options:
  --dry-run              Print planned changes without writing files.
  --yes                  Skip confirmation prompts.
  --target <path>        Install into a custom agent config directory.
  --rules-file <path>    Insert managed rule block into this file.
  --no-rules             Install project_memory only; do not modify or generate rules.
  --backup               Back up existing files before optional template updates.
  --force-template       Overwrite existing template/index/cloud files after backup.
  --help                 Show this help.
EOF
}

apm_say() {
  printf '%s\n' "$*"
}

apm_action() {
  local dry_run="$1"
  shift
  if [[ "$dry_run" == "1" ]]; then
    printf '[dry-run] %s\n' "$*"
  else
    printf '%s\n' "$*"
  fi
}

apm_confirm() {
  local yes="$1"
  local dry_run="$2"
  local target="$3"
  if [[ "$dry_run" == "1" || "$yes" == "1" ]]; then
    return 0
  fi
  printf 'Install Agent Project Memory into %s? [y/N] ' "$target"
  local reply=""
  read -r reply || true
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) apm_say "Cancelled."; return 1 ;;
  esac
}

apm_timestamp() {
  date +%Y%m%d%H%M%S
}

apm_backup_path() {
  local path="$1"
  printf '%s.backup.%s' "$path" "$(apm_timestamp)"
}

apm_backup_file() {
  local path="$1"
  local dry_run="$2"
  if [[ ! -e "$path" ]]; then
    return 0
  fi
  local backup
  backup="$(apm_backup_path "$path")"
  apm_action "$dry_run" "backup $path -> $backup"
  if [[ "$dry_run" != "1" ]]; then
    cp -p "$path" "$backup"
  fi
}

apm_mkdir() {
  local dir="$1"
  local dry_run="$2"
  apm_action "$dry_run" "mkdir -p $dir"
  if [[ "$dry_run" != "1" ]]; then
    mkdir -p "$dir"
  fi
}

apm_copy_template() {
  local src="$1"
  local dest="$2"
  local dry_run="$3"
  local backup="$4"
  local force_template="$5"
  local label="$6"

  if [[ -e "$dest" ]]; then
    if [[ "$force_template" == "1" ]]; then
      apm_backup_file "$dest" "$dry_run"
      apm_action "$dry_run" "overwrite $label $dest"
      if [[ "$dry_run" != "1" ]]; then
        cp "$src" "$dest"
      fi
    else
      if cmp -s "$src" "$dest" 2>/dev/null; then
        apm_action "$dry_run" "keep unchanged $label $dest"
      else
        apm_action "$dry_run" "skip existing $label $dest (use --force-template to replace)"
      fi
    fi
  else
    apm_action "$dry_run" "copy $label $src -> $dest"
    if [[ "$dry_run" != "1" ]]; then
      mkdir -p "$(dirname "$dest")"
      cp "$src" "$dest"
    fi
  fi

  if [[ "$backup" == "1" && "$force_template" != "1" && -e "$dest" ]]; then
    :
  fi
}

apm_build_managed_block() {
  printf '%s\n' "$APM_BEGIN"
  cat "$APM_REPO_ROOT/snippets/AGENT_RULE_BLOCK.md"
  printf '\n%s\n' "$APM_END"
}

apm_detect_rules_file() {
  local target="$1"
  local agent="$2"
  local explicit_rules="$3"

  if [[ -n "$explicit_rules" ]]; then
    printf '%s\n' "$explicit_rules"
    return 0
  fi

  local candidates=()
  case "$agent" in
    codex)
      candidates=("$target/AGENTS.md" "$target/CODEX.md" "$target/instructions.md")
      ;;
    claude)
      candidates=("$target/CLAUDE.md" "$target/instructions.md" "$target/AGENTS.md")
      ;;
    gemini)
      candidates=("$target/GEMINI.md" "$target/AGENTS.md" "$target/instructions.md")
      ;;
    *)
      candidates=("$target/AGENTS.md" "$target/instructions.md")
      ;;
  esac

  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

apm_write_managed_block() {
  local rules_file="$1"
  local dry_run="$2"
  local is_fallback="$3"

  local parent
  parent="$(dirname "$rules_file")"
  apm_action "$dry_run" "prepare rules file $rules_file"
  if [[ "$dry_run" != "1" ]]; then
    mkdir -p "$parent"
  fi

  if [[ "$dry_run" == "1" ]]; then
    if [[ "$is_fallback" == "1" ]]; then
      apm_action "$dry_run" "write manual rule block to $rules_file"
    else
      apm_action "$dry_run" "insert or replace managed rule block in $rules_file"
    fi
    return 0
  fi

  local block_file output_file
  block_file="$(mktemp)"
  output_file="$(mktemp)"
  apm_build_managed_block > "$block_file"

  if [[ ! -e "$rules_file" ]]; then
    cat "$block_file" > "$rules_file"
    rm -f "$block_file" "$output_file"
    return 0
  fi

  awk -v begin="$APM_BEGIN" -v end="$APM_END" -v block_file="$block_file" '
    BEGIN {
      while ((getline line < block_file) > 0) block = block line ORS
      in_block = 0
      replaced = 0
    }
    $0 == begin {
      if (!replaced) {
        printf "%s", block
        replaced = 1
      }
      in_block = 1
      next
    }
    $0 == end {
      in_block = 0
      next
    }
    !in_block { print }
    END {
      if (!replaced) {
        if (NR > 0) print ""
        printf "%s", block
      }
    }
  ' "$rules_file" > "$output_file"

  if cmp -s "$rules_file" "$output_file"; then
    apm_action 0 "managed rule block already up to date in $rules_file"
    rm -f "$block_file" "$output_file"
    return 0
  fi

  apm_backup_file "$rules_file" "$dry_run"
  mv "$output_file" "$rules_file"
  rm -f "$block_file"
}

install_project_memory() {
  local agent="generic"
  local default_target=""
  local target=""
  local rules_file=""
  local dry_run=0
  local yes=0
  local no_rules=0
  local backup=0
  local force_template=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent)
        agent="${2:-}"; shift 2 ;;
      --default-target)
        default_target="${2:-}"; shift 2 ;;
      --dry-run)
        dry_run=1; shift ;;
      --yes)
        yes=1; shift ;;
      --target)
        target="${2:-}"; shift 2 ;;
      --rules-file)
        rules_file="${2:-}"; shift 2 ;;
      --no-rules)
        no_rules=1; shift ;;
      --backup)
        backup=1; shift ;;
      --force-template)
        force_template=1; shift ;;
      --help|-h)
        apm_usage; return 0 ;;
      *)
        apm_say "Unknown option: $1" >&2
        apm_usage >&2
        return 2 ;;
    esac
  done

  if [[ -z "$target" ]]; then
    target="$default_target"
  fi
  if [[ -z "$target" ]]; then
    apm_say "No target directory provided." >&2
    return 2
  fi

  local memory_dir="$target/project_memory"

  apm_say "Agent Project Memory installer"
  apm_say "Agent: $agent"
  apm_say "Target: $target"
  if [[ "$dry_run" == "1" ]]; then
    apm_say "Mode: dry-run"
  fi

  apm_confirm "$yes" "$dry_run" "$target" || return 1

  apm_mkdir "$memory_dir/records" "$dry_run"
  apm_mkdir "$memory_dir/templates" "$dry_run"
  apm_mkdir "$memory_dir/archives" "$dry_run"

  apm_copy_template "$APM_REPO_ROOT/skills/project-memory/templates/INDEX.template.md" "$memory_dir/INDEX.md" "$dry_run" "$backup" "$force_template" "INDEX"
  apm_copy_template "$APM_REPO_ROOT/skills/project-memory/templates/CLOUD.template.md" "$memory_dir/CLOUD.md" "$dry_run" "$backup" "$force_template" "CLOUD"
  apm_copy_template "$APM_REPO_ROOT/skills/project-memory/templates/PROJECT_SUMMARY.template.md" "$memory_dir/templates/PROJECT_SUMMARY.template.md" "$dry_run" "$backup" "$force_template" "project template"
  apm_copy_template "$APM_REPO_ROOT/skills/project-memory/templates/ISSUE_SUMMARY.template.md" "$memory_dir/templates/ISSUE_SUMMARY.template.md" "$dry_run" "$backup" "$force_template" "issue template"
  apm_copy_template "$APM_REPO_ROOT/skills/project-memory/templates/RECOVERY.template.md" "$memory_dir/templates/RECOVERY.template.md" "$dry_run" "$backup" "$force_template" "recovery template"
  apm_copy_template "$APM_REPO_ROOT/.agent-memory-ignore" "$memory_dir/.agent-memory-ignore" "$dry_run" "$backup" "$force_template" "ignore file"

  if [[ "$no_rules" == "1" ]]; then
    apm_say "Rules installation skipped because --no-rules was used."
    return 0
  fi

  local detected_rules=""
  if detected_rules="$(apm_detect_rules_file "$target" "$agent" "$rules_file")"; then
    apm_write_managed_block "$detected_rules" "$dry_run" 0
    apm_say "Managed rule block installed into: $detected_rules"
  else
    local fallback="$target/PROJECT_MEMORY_RULES_TO_ADD.md"
    apm_write_managed_block "$fallback" "$dry_run" 1
    apm_say "No clear existing global rules file was found for $agent."
    apm_say "Manual rule block written to: $fallback"
    apm_say "Paste that managed block into your agent's global rules file."
  fi

  apm_say "Installed project_memory into: $memory_dir"
}
