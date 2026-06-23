# Agent Project Memory

Agent Project Memory is a local-first Codex plugin and portable Markdown memory system. It protects long-running work across interrupted sessions, keeps Git worktree checkpoints isolated, loads only the current project's memory, learns recurring feedback conservatively, and checks delivery evidence before an agent claims completion.

It remains usable by Claude Code, Gemini CLI, Cursor, OpenCode, and other Markdown-reading agents. Codex receives the full plugin, Hook, CLI, and continuity workflow; other agents keep the portable Markdown records and managed rule block.

## What it solves

- A session ends before `Stop` or compaction and the next session needs to continue.
- A new project should be protected without the user remembering `git init` or installing a Hook.
- Two worktrees from one repository must not share a latest checkpoint, lock, or debounce state.
- Project memory must load only after an exact project match.
- One correction must not become a permanent rule; matching feedback needs at least two distinct turns and no conflict.
- Delivery must fail when required evidence is missing, sensitive content is present, or normal Git state was polluted.

It cannot recover unwritten reasoning, an unfinished tool call, unsaved GUI state, or remote services that changed after a restart.

## Codex quick start

```bash
git clone https://github.com/Zss03040464/agent-project-memory.git
cd agent-project-memory

bash installers/install-codex.sh --dry-run
bash installers/install-codex.sh install --yes --backup
```

Windows PowerShell:

```powershell
git clone https://github.com/Zss03040464/agent-project-memory.git
Set-Location agent-project-memory

.\installers\install-codex.ps1 -DryRun
.\installers\install-codex.ps1 -Operation install -Yes -Backup
```

The Codex installer:

- installs the versioned plugin source under `~/plugins/agent-project-memory`;
- updates the personal marketplace without replacing unrelated entries;
- activates `agent-project-memory@personal` through the Codex CLI;
- provides `hooks/hooks.json`, the `project-memory` Skill, and a stable CLI launcher;
- creates private continuity and project-memory state;
- inserts one managed rule block while preserving user-authored rules;
- creates a restorable transaction snapshot.

Start a new Codex thread after install or upgrade so plugin components are rediscovered.

## Lifecycle commands

```bash
bash installers/install-codex.sh install --yes
bash installers/install-codex.sh upgrade --yes --backup
bash installers/uninstall.sh --yes
bash installers/install-codex.sh rollback --yes
```

PowerShell:

```powershell
.\installers\install-codex.ps1 -Operation install -Yes
.\installers\install-codex.ps1 -Operation upgrade -Yes -Backup
.\installers\uninstall.ps1 -Yes
.\installers\install-codex.ps1 -Operation rollback -Yes
```

Important options:

| Shell | PowerShell | Meaning |
| --- | --- | --- |
| `--dry-run` | `-DryRun` | Show the operation without writing. |
| `--target PATH` | `-TargetDir PATH` | Use another agent configuration directory. |
| `--home PATH` | `-HomeDir PATH` | Use another home for plugin source and marketplace. |
| `--backup` | `-Backup` | Include project-memory and continuity data in the restorable snapshot. |
| `--force-template` | `-ForceTemplate` | Replace only managed templates after making a timestamped copy. |
| `--migrate-v1-hook` | `-MigrateV1Hook` | Remove only the duplicate legacy user-Hook entry after plugin activation. |
| `--remove-data` | `-RemoveData` | On uninstall, also remove local project-memory and continuity data after backup. |

Default uninstall keeps user memory and continuity data. See [migration and uninstall](docs/migration-and-uninstall.md) before migrating v1 or removing data.

## Portable Markdown install

Claude Code and Gemini CLI retain the conservative Markdown installer:

```bash
bash installers/install-claude.sh --dry-run
bash installers/install-claude.sh --yes

bash installers/install-gemini.sh --dry-run
bash installers/install-gemini.sh --yes
```

The portable layout is:

```text
<agent-config>/project_memory/
  INDEX.md
  CLOUD.md
  records/
  templates/
  archives/
  .agent-memory-ignore
```

Existing `INDEX.md`, `CLOUD.md`, records, and user rules are preserved unless an explicit replacement option is used.

## How continuity works

The plugin records bounded, redacted turn state at several points rather than trusting one event:

- prompt submission opens the turn journal;
- completed tool use updates evidence and attempts a checkpoint;
- compaction and normal stop force a final checkpoint;
- a new session first freezes current disk state, then identifies an older open turn as interrupted and writes recovery files.

Git checkpoints use hidden refs and a temporary index. Normal branch, `HEAD`, worktree, and user staging must remain unchanged. Each worktree receives a separate identity, latest ref, history, lock, and debounce state. Safe dedicated projects may be initialized automatically; unsafe or untrusted non-Git projects use external checkpoint metadata instead.

Read [Codex continuity](docs/codex-continuity.md) and [recovery workflow](docs/recovery-workflow.md) for the exact inspection order and limits.

## Memory and control layers

- **Memory** stores stable reasons, preferences, decisions, and known traps.
- **Skill** stores repeatable workflows, commands, and checklists.
- **Profile** stores current-session identity and output constraints.
- **Project files** store current facts, plan, status, and handoff.
- **Continuity** stores in-progress evidence, checkpoint pointers, and recovery state.

Before work, route by canonical project identity and load only the matching record. Feedback is written to a private ledger; the same normalized intent needs evidence from at least two distinct turns in the same scope and no conflict before promotion. Before delivery, run the completion gate.

See [control loop](docs/control-loop.md).

## CLI

After installation:

```bash
agent-project-memory route --memory-root "$CODEX_HOME/project_memory" --cwd "$PWD" --json
agent-project-memory feedback record --help
agent-project-memory gate --help
```

The CLI is also available from a source checkout:

```bash
python3 scripts/apm.py --help
```

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src scripts tests
python3 scripts/privacy_scan.py
python3 scripts/validate_plugin.py .
bash scripts/smoke-test.sh
```

PowerShell:

```powershell
pwsh -NoProfile -File scripts/smoke-test.ps1
```

CI declares Ubuntu, macOS, and Windows runners for Python 3.9 and 3.14, runs real PowerShell on Windows, builds the package, scans archive listings, and validates plugin packaging.

The current local acceptance evidence is recorded in
[real install and recovery acceptance](docs/audits/2026-06-23-stage9-10-real-install-acceptance.md)
and [rollback and platform gate](docs/audits/2026-06-23-stage11-rollback-and-platform-gate.md).
Draft pull request [#1](https://github.com/Zss03040464/agent-project-memory/pull/1)
ran the full Ubuntu, macOS, Windows, Python 3.9/3.14, PowerShell, and package
matrix successfully.

## Security

The project is local-first and uploads nothing by itself. Do not put credentials, private keys, tokens, cookies, passwords, `auth.json`, sensitive `.env` content, browser profiles, or raw personal data into records, checkpoints, logs, fixtures, examples, or archives.

Recovery is inspect-first. Never automatically checkout a checkpoint, overwrite a worktree, push, or rewrite remote history. Read [security](docs/security.md) before changing filters or archive behavior.

## Development and publishing

Repository development uses an isolated branch/worktree and test-driven changes. Runtime Hook code remains standard-library-only. Do not push, open a pull request, merge, tag, or delete remote branches without explicit publication authorization.

See [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md),
[CHANGELOG.md](CHANGELOG.md), and the local
[2.0.0 release preparation](docs/release-2.0.0.md).
