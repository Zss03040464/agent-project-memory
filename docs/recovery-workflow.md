# Recovery Workflow

Recovery is evidence-first and non-destructive.

## Interrupted Codex work

Use this order:

1. Read the project's rules, task list, handoff, and user instructions in their declared order.
2. Read the current worktree's continuity `recovery.md` and `recovery.json`.
3. Capture current Git status, `HEAD`, branch, index tree, and worktree list.
4. Inspect only the current worktree's latest hidden checkpoint and compare it with the worktree.
5. Read a bounded transcript tail only when project files and continuity evidence cannot explain the state.
6. Revalidate remote services, GUI state, credentials, and other external conditions.
7. Update the task list and handoff before resuming costly work.
8. Continue without automatically checking out or overwriting anything.

An older `open` or `compacted` turn from another session may become `interrupted`. A `closed` turn does not mean the whole project is complete; it only means that turn ended normally.

## Missing project path

1. Route the current project memory by exact identity.
2. Read the linked project record and known canonical roots.
3. Search configured workspace roots and synchronized locations.
4. Check recorded Git remotes and default branch.
5. Check `CLOUD.md` and sanitized archive listings.
6. Report missing evidence before creating a replacement.

A missing path proves only that one path is missing.

## Restore a checkpoint

Do not reset or checkout over the current worktree. First create a separate recovery branch/worktree or export selected files from the checkpoint commit. Compare, test, and intentionally integrate only the required content.

## Restart limits

Project files, hidden refs, external checkpoint state, turn journals, routing records, and installer backups are disk-backed. They survive process and computer restart. Remote services, network tunnels, GUI windows, unsaved editor buffers, and unfinished model/tool state must be checked again after restart.
