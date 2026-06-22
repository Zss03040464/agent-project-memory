# Stage 4 Interrupted Turn Recovery Verification

Date: 2026-06-22 CST

Implementation commit:

```text
d8289bc feat: recover interrupted Codex turns
```

## State machine

- `UserPromptSubmit` freezes prior visible Git changes and sets `status=open`.
- `PostToolUse` stores only a tool category, safe paths, time, and checkpoint.
- `PreCompact` sets `status=compacted`.
- `Stop` sets `status=closed`; this is turn closure, not task completion.
- `SessionStart` freezes disk before reading old state. An `open` or
  `compacted` turn owned by another session becomes `interrupted`.
- Recovery can later be explicitly marked `recovered`.

Checkpoint failure is isolated from the journal. Open/interrupted state and
recovery files are still persisted when Git checkpoint creation fails.

## Persistent layout

```text
$CODEX_HOME/continuity/repos/<repo-id>/worktrees/<worktree-id>/
  turn.json
  events.jsonl
  recovery.json
  recovery.md
  turn.lock
```

The state includes schema version, session/turn ids, transcript pointer,
project/worktree identity, HEAD/branch, timestamps, prompt digest and safe
excerpt, tool category, safe changed paths, checkpoint evidence, and external
revalidation requirement.

## Recovery behavior

- Missed `PostToolUse`, compaction, and `Stop` are covered by the next
  `SessionStart` freeze.
- Session start reads only the current worktree state and checkpoint namespace.
- Recovery JSON contains structured evidence and fixed recovery order.
- Recovery Markdown warns that unpersisted thoughts, unfinished calls, and GUI
  state cannot be recovered.
- Transcript indexing is best effort and stores metadata only.
- Hook output uses official structured `SessionStart.additionalContext`.
- Hook failures are non-blocking and privacy-safe.

## Fresh verification

```text
Python 3.9: 80 tests, 0 failures
Python 3.14: 80 tests, 0 failures
compileall: passed on both runtimes
privacy scan: passed
git diff --check: passed
```

A two-process probe invoked the Hook module separately for
`UserPromptSubmit` and `SessionStart`. The second process found the persisted
open turn, froze the intervening disk change, generated recovery files, and
returned recovery context. The path does not depend on same-process memory.
