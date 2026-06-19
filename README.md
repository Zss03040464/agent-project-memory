# Agent Project Memory

Agent Project Memory is a local-first memory and recovery workflow for coding agents.

It gives Codex, Claude Code, Gemini CLI, Cursor, OpenCode, and other Markdown-readable agents a small project memory layout that can be installed into an agent config directory and checked before an agent recreates missing projects, repeats old troubleshooting, overwrites recovered work, or loses context after a path or session change.

Status: usable MVP, actively improving installers and documentation.

## What this is

Agent Project Memory is a local-first Agent memory rules package, template set, installer, and recovery workflow.

It installs this structure into an agent configuration directory:

```text
<agent-config>/project_memory/
  INDEX.md
  CLOUD.md
  records/
  templates/
    PROJECT_SUMMARY.template.md
    ISSUE_SUMMARY.template.md
    RECOVERY.template.md
  archives/
  .agent-memory-ignore
```

The global rule block tells the agent to read `project_memory/INDEX.md`, linked files under `records/`, `CLOUD.md`, and recovery templates before acting on project setup, repair, migration, path-loss, sync, or backup-recovery tasks.

## What this is not

This project is not a database, vector memory service, cloud sync daemon, telemetry system, secret manager, automatic archive uploader, or replacement for Git. It does not claim to be a fully automated long-term memory service.

## Supported tools

- Codex
- Claude Code
- Gemini CLI
- Cursor / OpenCode / other agents that can read local Markdown rules and files

The installers are intentionally conservative. If they cannot identify a clear existing global rules file, they still install `project_memory/` and generate `PROJECT_MEMORY_RULES_TO_ADD.md` for manual paste into the agent's global rules.

## 30-second quick start

```bash
git clone https://github.com/Zss03040464/agent-project-memory.git
cd agent-project-memory

bash installers/install-codex.sh --dry-run
bash installers/install-codex.sh --yes

# or
bash installers/install-claude.sh --dry-run
bash installers/install-claude.sh --yes

# or
bash installers/install-gemini.sh --dry-run
bash installers/install-gemini.sh --yes
```

Windows PowerShell:

```powershell
git clone https://github.com/Zss03040464/agent-project-memory.git
cd agent-project-memory

.\installers\install-codex.ps1 -DryRun
.\installers\install-codex.ps1 -Yes

# or
.\installers\install-claude.ps1 -DryRun
.\installers\install-claude.ps1 -Yes

# or
.\installers\install-gemini.ps1 -DryRun
.\installers\install-gemini.ps1 -Yes
```

## Install options

macOS / Linux installers support:

```text
--dry-run           print planned changes without writing files
--yes               skip confirmation prompts
--target <path>     install into a custom agent config directory
--rules-file <path> insert the managed rule block into a specific global rules file
--no-rules          install project_memory only; do not touch or generate rule files
--backup            back up existing files before optional template updates
--force-template    overwrite template/index/cloud files from repository templates after backup
```

PowerShell installers support equivalent options:

```text
-DryRun
-Yes
-TargetDir <path>
-RulesFile <path>
-NoRules
-Backup
-ForceTemplate
```

All installers are designed to be idempotent. Re-running the same install command should not duplicate the managed rule block or overwrite existing user `INDEX.md` / `CLOUD.md` files by default.

## Codex installation

Default target:

```bash
bash installers/install-codex.sh --dry-run
bash installers/install-codex.sh --yes
```

Custom target:

```bash
bash installers/install-codex.sh --target /path/to/.codex --dry-run
bash installers/install-codex.sh --target /path/to/.codex --yes
```

PowerShell:

```powershell
.\installers\install-codex.ps1 -DryRun
.\installers\install-codex.ps1 -Yes
.\installers\install-codex.ps1 -TargetDir C:\agent-config\.codex -Yes
```

The Codex installer looks for an existing Markdown rules file inside the target directory, such as `AGENTS.md`, `CODEX.md`, or `instructions.md`. If none exists, it writes `PROJECT_MEMORY_RULES_TO_ADD.md` and prints the next step.

## Claude Code installation

```bash
bash installers/install-claude.sh --dry-run
bash installers/install-claude.sh --yes
```

PowerShell:

```powershell
.\installers\install-claude.ps1 -DryRun
.\installers\install-claude.ps1 -Yes
```

The Claude installer looks for an existing Markdown rules file inside the target directory, such as `CLAUDE.md`, `instructions.md`, or `AGENTS.md`. If none exists, it writes `PROJECT_MEMORY_RULES_TO_ADD.md`.

## Gemini CLI installation

```bash
bash installers/install-gemini.sh --dry-run
bash installers/install-gemini.sh --yes
```

PowerShell:

```powershell
.\installers\install-gemini.ps1 -DryRun
.\installers\install-gemini.ps1 -Yes
```

The Gemini installer looks for an existing Markdown rules file inside the target directory, such as `GEMINI.md` or `AGENTS.md`. If none exists, it writes `PROJECT_MEMORY_RULES_TO_ADD.md`.

## Explicit rule-file installation

If you already know the correct global rules file for your agent, pass it explicitly:

```bash
bash installers/install-codex.sh --target ~/.codex --rules-file ~/.codex/AGENTS.md --yes
```

```powershell
.\installers\install-codex.ps1 -TargetDir $HOME\.codex -RulesFile $HOME\.codex\AGENTS.md -Yes
```

The installer inserts or replaces only this managed block:

```text
<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->
...
<!-- END AGENT_PROJECT_MEMORY_RULES -->
```

Existing content outside the managed block is preserved. Existing rules files are backed up before modification.

## Verify installation

After installation, verify that the memory files exist:

```bash
find ~/.codex/project_memory -maxdepth 3 -type f | sort
```

Expected core files:

```text
project_memory/INDEX.md
project_memory/CLOUD.md
project_memory/.agent-memory-ignore
project_memory/templates/PROJECT_SUMMARY.template.md
project_memory/templates/ISSUE_SUMMARY.template.md
project_memory/templates/RECOVERY.template.md
```

If a rules file was found or passed explicitly, verify that the managed block appears exactly once:

```bash
grep -R "BEGIN AGENT_PROJECT_MEMORY_RULES" ~/.codex ~/.claude ~/.gemini 2>/dev/null
```

If the installer created `PROJECT_MEMORY_RULES_TO_ADD.md`, open that file and paste the whole managed block into your agent's global rules file.

## Smoke test

Run the cross-platform installer tests locally:

```bash
bash scripts/smoke-test.sh
```

PowerShell smoke test, when `pwsh` is available:

```powershell
pwsh -NoProfile -File scripts/smoke-test.ps1
```

The tests install into temporary directories, verify idempotency, confirm dry-run does not write files, confirm existing `INDEX.md` is not overwritten, and confirm uninstall removes only the managed block unless memory removal is explicitly requested.

## Real usage examples

See `examples/simple-project/` for a sanitized example.

### New project record

1. Add a concise entry to `project_memory/INDEX.md`.
2. Create a folder under `project_memory/records/<project-slug>/`.
3. Copy `project_memory/templates/PROJECT_SUMMARY.template.md` to `project_memory/records/<project-slug>/SUMMARY.md`.
4. Fill in purpose, known paths, key files, environment, decisions, completed work, and recovery entry point.

Example index entry:

```markdown
### Web Dashboard

- Type: project
- Status: active
- Keywords: web, dashboard, frontend, api
- Record: `records/sample-web-dashboard/SUMMARY.md`
- Cloud mirror: see `CLOUD.md`
```

### Record a solved issue

1. Copy `ISSUE_SUMMARY.template.md` to a record folder such as `records/sample-proxy-issue/SUMMARY.md`.
2. Record symptoms, confirmed root cause, resolution, verification, and actions that future agents must not repeat.
3. Link the issue record from `INDEX.md`.

### Recover when a project path is missing

Ask the agent to follow the installed recovery rule:

```text
Before creating a replacement project, read project_memory/INDEX.md, the linked record under records/, CLOUD.md, and RECOVERY.template.md. Check known paths, workspace roots, sync folders, Git remotes, cloud mirrors, and sanitized archives. Report evidence before creating anything new.
```

### Cloud backup records without leaking privacy

Use `CLOUD.md` to record generic cloud references and archive names. Do not store passwords, API keys, private keys, emails, tokens, or raw personal data. Prefer placeholders or non-sensitive names when publishing examples.

Example:

```text
Cloud root: CloudDrive/Agent_Project_Memory/
Archive: sample-web-dashboard_2026-01_stable.zip
```

## Security

Do not store:

- API keys
- private keys
- passwords
- access tokens or refresh tokens
- account cookies
- browser profiles
- credential JSON files
- raw personal data
- private machine-specific paths in public examples

This project does not upload anything by itself. Cloud references are only notes that tell an agent where to look if local memory or project paths are missing.

Use `.agent-memory-ignore` before making any archive. Review the archive file list before placing an archive in cloud storage.

## Rollback and uninstall

Default uninstall removes only the managed rule block and keeps `project_memory/` data:

```bash
bash installers/uninstall.sh --target ~/.codex --yes
```

PowerShell:

```powershell
.\installers\uninstall.ps1 -TargetDir $HOME\.codex -Yes
```

To remove memory files as well, pass the explicit remove option:

```bash
bash installers/uninstall.sh --target ~/.codex --remove-memory --yes
```

```powershell
.\installers\uninstall.ps1 -TargetDir $HOME\.codex -RemoveMemory -Yes
```

Before modifying a rules file or deleting memory data, uninstall creates a timestamped backup.

## FAQ

### Installation succeeded, but the agent does not read the memory. What should I do?

Check whether the installer found a real global rules file. If it created `PROJECT_MEMORY_RULES_TO_ADD.md`, paste the entire managed block into the global rules file used by your agent. Then restart the agent session and ask it to read `project_memory/INDEX.md` before acting.

### What if paths differ across machines?

Use stable project slugs, Git remotes, generic workspace roots, and cloud mirror references. Avoid hard-coding private machine paths in shared examples. Let each machine's record list its own local path only if it is safe and useful.

### How do I install on Windows?

Use PowerShell from the repository root:

```powershell
.\installers\install-codex.ps1 -DryRun
.\installers\install-codex.ps1 -Yes
```

Use `-TargetDir` for custom config locations.

### Will existing INDEX.md or CLOUD.md be overwritten?

No. By default, existing `INDEX.md` and `CLOUD.md` are preserved. To replace them with repository templates, use `--force-template` or `-ForceTemplate`; existing files are backed up first.

### Is this a database?

No. It is a Markdown-based local memory and recovery workflow. It is deliberately simple so agents and humans can inspect it directly.

### Can it sync multiple devices?

It can record cloud mirror locations and sanitized archive names, but it does not sync files automatically. Use your own sync tool or Git workflow, and keep secrets out of memory records and archives.

## Project layout

```text
installers/              install and uninstall scripts
snippets/                managed global rule block content
skills/project-memory/   skill-style instructions and templates
examples/simple-project/ sanitized usage example
tests/                   installer smoke tests
scripts/                 local smoke test wrappers
.github/workflows/       CI workflow
```

## License

MIT
