# Stage 8 plugin, installer, safety, and CI audit

Date: 2026-06-22 CST

## Implemented

- Valid Codex plugin manifest using default Hook discovery.
- SessionStart, UserPromptSubmit, PostToolUse, PreCompact, and Stop plugin Hooks with Unix and Windows commands rooted at `PLUGIN_ROOT`.
- Discoverable project-memory Skill, bundled standard-library Hook runtime, and CLI.
- Exact-project feedforward with profile and scoped confirmed corrections; repository/worktree fallback refresh; moved-root and remote history.
- Feedback timestamps, distinct evidence threshold, destination artifact, conflict blocking, and active rollback state.
- Git baseline snapshot and evidence completion gate CLI.
- Transactional install, upgrade, uninstall, rollback, and explicit v1 Hook migration in shell and PowerShell.
- Expanded privacy scan and package/plugin validators.
- Ubuntu/macOS/Windows and Python 3.9/3.14 CI declarations plus package build.
- Updated design, continuity, control-loop, security, recovery, migration, uninstall, README, changelog, and contribution guidance.

## Fresh verification

- Python 3.14: 119 tests passed.
- macOS system Python 3.9: 119 tests passed.
- Both runtimes passed `compileall`.
- Shell smoke test: 8 tests passed.
- PowerShell 7.7 preview isolated runtime: dry-run, install, upgrade, uninstall, Unicode/space path, and data-preservation smoke passed.
- Repository validator passed.
- Current system plugin-creator validator passed in an isolated PyYAML virtual environment.
- Wheel and source archive built without the earlier license deprecation warning; wheel CLI launched.
- Privacy scan, README local-link check, and `git diff --check` passed.

## Boundaries still requiring later-stage evidence

- The GitHub workflow is not pushed, so a real GitHub Windows runner has not executed this commit. The workflow does not skip PowerShell; local isolated PowerShell evidence is recorded above.
- Real Codex Hook discovery/trust, v1 duplicate deactivation, process restart, qimo/worktree inspection, and rollback drill remain phases 9–11.
- No push, pull request, merge, tag, remote-branch deletion, or remote-history rewrite occurred.
