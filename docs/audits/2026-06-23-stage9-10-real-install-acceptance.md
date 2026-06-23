# Stage 9–10 Real Install and Recovery Acceptance

Date: 2026-06-23 CST

Branch: `feat/codex-continuity-v2`

Relevant commits:

```text
db5f286 feat: package continuity plugin and lifecycle tools
7fc6354 fix: keep installed memory state private
6eb7a15 fix: anchor clean worktree checkpoint refs
62e28c6 test: keep public audits machine-neutral
```

No push, pull request, merge, remote tag, or remote-history rewrite was
performed.

## Installation and discovery

- Install, upgrade, uninstall, and rollback passed in an isolated HOME and
  CODEX_HOME.
- The real installation was performed only from clean local commits and wrote
  transaction snapshots below `$CODEX_HOME/backups/agent-project-memory/`.
- Codex discovered `agent-project-memory@personal` version 2.0.0 and the
  namespaced `agent-project-memory:project-memory` Skill.
- The normal Codex trust UI was used. No hook-trust bypass flag was used.
- Fresh app-server inspection found exactly five plugin Hooks, all trusted:
  `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `PreCompact`, and `Stop`.
- The migrated v1 user Hook count is zero. The old script and legacy refs remain
  available for rollback but are no longer registered.
- Project memory, continuity state, and their owned children have private 0700
  directory modes. This was found by real installation, reproduced by a failing
  test, and fixed before reinstalling.
- The global rules document was 8,836 bytes at installation validation, with
  one managed rule block, well below the Codex project-instruction limit.

## Automated recovery matrix

The final pre-report run passed on Python 3.9 and Python 3.14:

```text
121 tests, 0 failures on each runtime
compileall passed on each runtime
shell smoke: 8 tests, 0 failures
privacy scan passed
git diff --check passed
```

An isolated multi-process probe used the installed Hook launcher and verified:

- `UserPromptSubmit` persisted an open turn.
- The first process exited without `PostToolUse`, `PreCompact`, or `Stop`.
- A file changed after that process exited.
- A new `SessionStart` process froze the changed disk state, classified the old
  turn as interrupted, and generated recovery JSON and Markdown.
- A trusted marked project was automatically initialized as Git without a
  commit or remote.
- An established non-Git project outside trusted roots received an external
  checkpoint and no `.git` directory.
- A fake sensitive `.env` value was absent from the checkpoint and journal,
  while a safe file was checkpointed.
- Feedback still required two distinct turn/session observations in one scope;
  the completion gate still rejected missing evidence, sensitive content, and
  normal Git-state pollution.

## Real repository and worktree safety

A real Git checkout with one existing user status record and a clean detached
Codex-managed worktree were fingerprinted before and after Hook execution.
For both locations, all of these values were identical before and after:

- `git status --porcelain=v2` hash;
- HEAD;
- branch or detached state;
- normal index tree;
- `git worktree list --porcelain` hash.

No normal commit, push, cleanup, checkout, or index write was performed.
Generated, ignored, browser-state, and sensitive paths remained excluded.

The two locations share one Git common directory but have different stable
worktree ids, latest refs, locks, debounce state, and continuity journals. A
clean worktree initially exposed a missing-baseline edge case; the final
implementation now anchors its own `latest` to the existing HEAD without
creating a commit or touching normal Git state.

## Full Codex restart

The first desktop quit closed only the main window, so it was not accepted as
evidence. The acceptance was repeated by terminating the complete Codex
application process group with SIGTERM, then launching Codex again.

After restart:

- a new Codex main process had a new PID and start time;
- the new session received the interrupted-turn recovery context;
- the recovery ref and commit still resolved;
- current project management files matched the recovery checkpoint;
- the normal repository remained unborn with an empty normal index;
- app-server discovery still found five trusted plugin Hooks, zero legacy user
  Hooks, and zero Hook errors;
- legacy v1 ref count did not increase after the fresh process loaded the
  migrated configuration.

The model request itself was rejected by the account usage limit, but Hook
recovery completed before the model call. This separates continuity evidence
from model availability and is a useful failure-mode acceptance result.

## Platform evidence and remaining boundary

- macOS execution, both supported Python runtimes, POSIX shell lifecycle, and
  real Codex discovery/restart were exercised locally.
- PowerShell 7.7 preview executed dry-run, install, upgrade, and uninstall in an
  isolated environment, including Unicode and spaced paths.
- CI declares Ubuntu, macOS, and Windows with Python 3.9 and 3.14; the Windows
  job runs the PowerShell smoke test without a skip branch.
- The current branch has not been pushed, by explicit safety requirement, so no
  remote Windows runner result is claimed. Windows CI must run after a future
  explicitly authorized push or pull request.

## Capability boundary

Recovery reaches the latest persisted and verifiable evidence. It cannot
recover private model reasoning, unsaved edits, unfinished tool calls, or
external GUI/network/service state that changed after interruption. Those must
be re-executed or revalidated.
