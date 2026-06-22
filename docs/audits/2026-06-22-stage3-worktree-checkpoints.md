# Stage 3 Worktree Checkpoint Verification

Date: 2026-06-22 CST

Implementation commit:

```text
bdf2842 feat: isolate checkpoints by git worktree
```

## Identity and refs

- `repo_id` is derived from the canonical Git common directory.
- `worktree_id` is derived from canonical worktree root plus worktree Git
  directory.
- Branch switches and detached HEAD do not change the worktree identity.
- Two worktrees sharing a common directory receive different worktree ids.
- Refs use:

```text
refs/codex/checkpoints/worktrees/<worktree-id>/latest
refs/codex/checkpoints/worktrees/<worktree-id>/history/<timestamp>-<tree>
```

- Lock, debounce state, and temporary index live under the current worktree
  Git directory, not one repo-global state path.
- Legacy v1 refs remain read-only and are reported as migration hints.

## Safety behavior

- The user's branch, HEAD, normal index, staged content, and worktree files are
  unchanged by checkpoint creation.
- A separate temporary index builds the checkpoint tree.
- Ignored, sensitive, generated, nested-repository, oversized, and
  sensitive-content candidates are excluded.
- A modified tracked sensitive file retains its committed HEAD version instead
  of leaking the working copy.
- Symlinks are saved as symlinks without reading their external targets.
- Git LFS-marked files use the configured clean filter and are not rejected
  solely for raw worktree size.
- Unborn repositories produce parentless checkpoint commits.
- Detached HEAD and branch-switch states produce valid checkpoints under the
  same worktree ref namespace.
- Concurrent calls serialize per worktree; duplicate trees are not repeated;
  retention pruning is scoped to that worktree.
- Removing a linked worktree leaves its hidden refs inspectable and does not
  affect the primary checkout.

## Fresh verification

```text
/usr/bin/python3 -m unittest discover -s tests -v
67 tests, 0 failures

/opt/homebrew/bin/python3 -m unittest discover -s tests -v
67 tests, 0 failures

compileall for both Python runtimes
passed

privacy scan
passed

git diff --check
passed
```

Real qimo and Codex-managed worktree verification remains intentionally
deferred to stage 10, after the Hook state machine and installation path are
complete.
