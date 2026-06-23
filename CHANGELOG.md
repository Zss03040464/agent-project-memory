# Changelog

## 2.0.0 - Unreleased

- Added a Codex plugin manifest, default continuity Hooks, and discoverable project-memory Skill.
- Added worktree-isolated hidden checkpoints and external checkpoints for protected non-Git projects.
- Added persistent turn journals and interruption recovery across process restarts.
- Added safe project bootstrap, exact-project memory routing, evidence-counted feedback promotion, rollback, and a completion gate.
- Added transactional install, upgrade, uninstall, rollback, and explicit v1 Hook migration for shell and PowerShell.
- Expanded privacy scanning to HTML, JSON, common configuration, archive listings/text, and binary metadata without printing matched values.
- Added Ubuntu, macOS, Windows, Python 3.9/3.14, package, plugin, shell, and PowerShell CI declarations.
- Enforced private permissions for installed project-memory state and added a regression test for machine-specific paths in public audits.
- Anchored a clean worktree's first hidden `latest` ref to its existing HEAD without creating a commit or changing normal Git state.
- Completed isolated rollback, real Linux, PowerShell, real repository/worktree, and full Codex restart acceptance.

## 0.2.0

- Made shell and PowerShell installers idempotent.
- Added dry-run, target, no-rules, backup, force-template, and explicit rules-file options.
- Added managed rule block insertion and replacement.
- Added safe uninstall scripts.
- Added smoke tests and GitHub Actions CI.
- Rewrote README for clone, install, verify, rollback, and real usage workflows.
- Added sanitized examples under `examples/simple-project/`.

## 0.1.0

- Initial public release.
- Added Project Memory skill.
- Added local index, cloud backup, project summary, issue summary, and recovery templates.
- Added example memory records using fictional placeholder projects only.
- Added Codex, Claude Code, and Gemini CLI installers.
- Added security guidance and default archive ignore file.
