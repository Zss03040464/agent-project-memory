# Agent Project Memory

Portable project memory for coding agents.

Agent Project Memory gives coding agents a durable, local-first memory structure for recovering project context, avoiding repeated troubleshooting, locating renamed or moved projects, and checking cloud backups before recreating or overwriting missing work.

It is designed for Claude Code, Codex, Gemini CLI, Cursor, OpenCode, and any coding agent that can read local Markdown files.

## Why this exists

Coding agents often lose useful context when:

- a project folder is renamed or moved
- a sync tool changes paths
- an agent session is reset
- a different agent tool is used later
- a local workspace is damaged
- a previous debugging conclusion is forgotten
- an agent sees a missing path and creates a new empty project over the expected location

This repository provides a small, explicit memory system:

```text
project_memory/
  INDEX.md          # high-level registry of known projects and solved issues
  CLOUD.md          # cloud backup and recovery locations
  records/          # per-project and per-issue records
  templates/        # templates for new records
  archives/         # optional local placeholder for full project archives
```

## Core rule

A missing local path is not proof that a project is gone.

Before creating, replacing, or overwriting a project, an agent must check the local memory index, project records, known workspace paths, sync folders, Git remotes, and cloud backup references.

## What this is

Agent Project Memory is:

- a skill-style instruction pack
- a project registry format
- a set of Markdown templates
- a recovery workflow
- install scripts for common agent config folders
- a security-first convention for cloud backups and project archives

## What this is not

Agent Project Memory is not:

- a database server
- a telemetry system
- a secret manager
- an automatic cloud uploader
- a replacement for Git
- a guarantee that deleted files can always be recovered

## Quick start

Clone or download this repository, then install into the agent you use.

### Codex

```bash
bash installers/install-codex.sh
```

PowerShell:

```powershell
.\installers\install-codex.ps1
```

### Claude Code

```bash
bash installers/install-claude.sh
```

PowerShell:

```powershell
.\installers\install-claude.ps1
```

### Gemini CLI

```bash
bash installers/install-gemini.sh
```

PowerShell:

```powershell
.\installers\install-gemini.ps1
```

The installer copies templates into the matching agent configuration folder and prints the rule block that must be added to the agent's global rules file.

## Manual installation

Create this directory inside your agent config folder:

```text
<agent-config>/project_memory/
```

Copy:

```text
skills/project-memory/templates/INDEX.template.md      -> project_memory/INDEX.md
skills/project-memory/templates/CLOUD.template.md      -> project_memory/CLOUD.md
skills/project-memory/templates/PROJECT_SUMMARY.template.md -> project_memory/templates/PROJECT_SUMMARY.template.md
skills/project-memory/templates/ISSUE_SUMMARY.template.md   -> project_memory/templates/ISSUE_SUMMARY.template.md
skills/project-memory/templates/RECOVERY.template.md        -> project_memory/templates/RECOVERY.template.md
```

Then add the rule block from `snippets/AGENT_RULE_BLOCK.md` to your agent's global rules file.

## Recommended cloud layout

Use a cloud drive folder only for generic memory files and sanitized archives:

```text
Agent_Project_Memory/
  INDEX.md
  CLOUD.md
  records/
  archives/
```

Do not upload secrets, private keys, token files, credential files, or unfiltered dependency caches.

## Security first

Before archiving any project, review `.agent-memory-ignore` and `docs/security.md`.

Default excluded patterns include:

```text
.env
.env.*
*.key
*.pem
id_rsa
id_ed25519
credentials.json
token.json
node_modules/
.venv/
venv/
.git/
__pycache__/
dist/
build/
out/
.cache/
```

## Example record

The example records use fictional projects only. They do not contain real user data, real device names, real project paths, tokens, emails, or private repository names.

See `examples/project_memory/`.

## License

MIT
