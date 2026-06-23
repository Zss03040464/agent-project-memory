# Agent Project Memory 2.0.0 Release Preparation

Status: draft pull request #1; not merged or released.

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

- macOS Python 3.9 and 3.14: 125 tests on each runtime;
- GitHub-hosted Ubuntu, macOS, and Windows runners: Python 3.9 and 3.14
  matrix passed, including native PowerShell lifecycle smoke on Windows;
- Ubuntu x86_64 Python 3.12: 121 tests;
- PowerShell 7.6.3: lifecycle smoke passed;
- real Codex install, trust, restart, interruption recovery, and Skill discovery
  passed;
- real checkout plus detached Codex worktree remained unchanged outside hidden
  refs and private continuity state;
- package, plugin, privacy, documentation-link, and Git-state gates passed.
- the clean release candidate passed its own completion gate; detector source
  and fake test fixtures no longer create false positives, while real sensitive
  paths, high-confidence credentials, and configuration assignments still
  block delivery.
- snapshot and completion-gate baselines work in safely initialized projects
  before their first normal commit.

See the stage 9–11 and final delivery audit reports for exact limits. Draft
pull request [#1](https://github.com/Zss03040464/agent-project-memory/pull/1)
is the first remote publication of this branch and all declared checks passed.

## Publication status

Published branch:

```text
feat/codex-continuity-v2
PR: https://github.com/Zss03040464/agent-project-memory/pull/1
```

The pull request remains draft. Do not merge, tag, release, or delete branches
until separately authorized.
