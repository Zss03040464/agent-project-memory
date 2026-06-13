#!/usr/bin/env bash
set -euo pipefail

install_project_memory() {
  local target_dir="$1"
  local repo_root
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  mkdir -p "$target_dir/project_memory/records"
  mkdir -p "$target_dir/project_memory/templates"
  mkdir -p "$target_dir/project_memory/archives"

  cp "$repo_root/skills/project-memory/templates/INDEX.template.md" "$target_dir/project_memory/INDEX.md"
  cp "$repo_root/skills/project-memory/templates/CLOUD.template.md" "$target_dir/project_memory/CLOUD.md"
  cp "$repo_root/skills/project-memory/templates/PROJECT_SUMMARY.template.md" "$target_dir/project_memory/templates/PROJECT_SUMMARY.template.md"
  cp "$repo_root/skills/project-memory/templates/ISSUE_SUMMARY.template.md" "$target_dir/project_memory/templates/ISSUE_SUMMARY.template.md"
  cp "$repo_root/skills/project-memory/templates/RECOVERY.template.md" "$target_dir/project_memory/templates/RECOVERY.template.md"
  cp "$repo_root/.agent-memory-ignore" "$target_dir/project_memory/.agent-memory-ignore"

  echo "Installed project_memory into: $target_dir/project_memory"
  echo ""
  echo "Add the following rule block to your agent global rules file:"
  echo ""
  cat "$repo_root/snippets/AGENT_RULE_BLOCK.md"
}
