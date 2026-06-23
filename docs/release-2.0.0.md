# Agent Project Memory 2.0.0 Release Preparation

Status: local release candidate; not published.

## Highlights

- Versioned Codex plugin with five trusted continuity Hooks and one namespaced
  project-memory Skill.
- Persistent interrupted-turn recovery that does not depend on `Stop`,
  compaction, or one specific tool event.
- Safe automatic Git bootstrap plus external checkpoints for protected non-Git
  projects.
- Per-worktree refs, locks, debounce state, journals, and recovery pointers.
- Exact-project feedforward, two-observation feedback promotion, layered
  Memory/Skill/Profile/project/continuity responsibilities, and a completion
  gate.
- Transactional shell and PowerShell install, upgrade, uninstall, v1 migration,
  and rollback.

## Local release candidate evidence

- macOS Python 3.9 and 3.14: 121 tests on each runtime;
- Ubuntu x86_64 Python 3.12: 121 tests;
- PowerShell 7.6.3: lifecycle smoke passed;
- real Codex install, trust, restart, interruption recovery, and Skill discovery
  passed;
- real checkout plus detached Codex worktree remained unchanged outside hidden
  refs and private continuity state;
- package, plugin, privacy, documentation-link, and Git-state gates passed.

See the stage 9–11 audit reports for exact limits. The current branch has not
run on a remote Windows runner because it has not been pushed.

## Publication commands — do not run without explicit authorization

Review locally first:

```bash
git status --short
git log --oneline main..feat/codex-continuity-v2
git diff --stat main...feat/codex-continuity-v2
```

After the user separately authorizes publication:

```bash
git push -u origin feat/codex-continuity-v2
gh pr create \
  --repo Zss03040464/agent-project-memory \
  --base main \
  --head feat/codex-continuity-v2 \
  --draft \
  --title "Agent Project Memory 2.0.0: Codex continuity and recovery" \
  --body-file docs/release-2.0.0.md
```

Wait for Ubuntu, macOS, Windows/PowerShell, package, privacy, and plugin checks.
Do not merge, tag, or delete remote branches until separately authorized.
