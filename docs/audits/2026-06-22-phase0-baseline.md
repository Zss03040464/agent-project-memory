# Phase 0 and 1 Baseline Audit

Date: 2026-06-22 CST

## Repository

- Repository: `Zss03040464/agent-project-memory`
- Default branch: `main`
- Baseline commit: `8d8a746cb430cda53ea61539ccb6fbd8b2c44291`
- Development branch: `feat/codex-continuity-v2`
- Development worktree:
  `$HOME/.config/superpowers/worktrees/agent-project-memory/feat-codex-continuity-v2`
- Latest observed CI run for baseline commit: successful Ubuntu `CI` workflow,
  run `27818870511`.
- Release: none.
- The old `make-installable-and-verifiable` branch is one commit behind `main`.

No push, pull request, merge, tag, remote branch deletion, or remote-history
rewrite was performed.

## Current Codex facts

- Installed CLI: `codex-cli 0.142.0-alpha.6`.
- Stable enabled mechanisms include hooks, plugins, multi-agent, goals,
  unified exec, and remote compaction v2.
- Memories remain experimental and are enabled locally.
- User-level hooks load independently of project trust.
- Matching hooks from user and plugin sources all run; plugin migration must
  prevent duplicate lifecycle handlers.
- Non-managed hook definitions are trusted by exact hash and changed hooks must
  be reviewed again.
- Installed version schemas provide `session_id`, `turn_id`,
  `transcript_path`, and `cwd` to the required turn-scoped events.
- `SessionStart` can return structured `additionalContext`.
- Codex-managed worktrees normally use detached HEADs under
  `$CODEX_HOME/worktrees` and share Git common metadata.
- Skills are discovered from repository `.agents/skills`, user
  `$HOME/.agents/skills`, admin, system, and enabled plugin locations.
- `AGENTS.md` guidance is loaded at session start and has a default combined
  project-document limit of 32 KiB.
- Memories are generated asynchronously and are not a required-rule or
  continuity source.
- Resuming a session retains the original transcript; a new thread does not
  automatically inherit an old transcript.

Official evidence was taken from the current Codex manual and the generated
Hook JSON schemas at tag `rust-v0.142.0-alpha.6`.

## Local baseline

- Existing v1 checkpoint tests: 24 passed.
- Repository installer tests: 8 passed.
- Shell smoke test: passed.
- Shell syntax checks: passed.
- Privacy scan: passed.
- PowerShell executable: unavailable locally; this remains unverified until a
  real Windows/PowerShell CI job passes.
- Baseline worktree was clean before this audit document and `AGENTS.md` were
  added.

## Confirmed repository gaps

- No `.codex-plugin/plugin.json`.
- No repository `AGENTS.md` before this branch.
- The current Codex installer does not install the Skill into an official
  discovery path.
- The installed global rule block uses cwd-relative `project_memory/...`
  paths.
- The current `--backup` switch is parsed but has no effective behavior unless
  template replacement independently triggers a backup.
- The CI workflow only runs on Ubuntu and conditionally skips PowerShell.
- Tests cover installer file existence and idempotency, not hook discovery,
  hook trust, restart recovery, worktree isolation, abnormal interruption,
  non-Git external checkpoints, routing, feedback promotion, or completion
  gating.
- The current privacy scan covers only a narrow text suffix and regex set.
- There is no package, continuity state machine, automatic project bootstrap,
  recovery CLI, feedback ledger, completion gate, plugin lifecycle migration,
  or rollback integration test.

## Global backup

Backup directory:

`$CODEX_HOME/backups/codex-continuity-v2-20260622_152110_CST`

The backup contains the existing global rules, config, Hook configuration and
script, rules appendix, and this task project's four management files.
`MANIFEST.sha256`, a permissions inventory, absent-path inventory, and
per-file verification report were generated. All nine copied files matched
their source hashes and modes.
