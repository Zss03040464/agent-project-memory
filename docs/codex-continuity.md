# Codex Continuity

The plugin listens to multiple stable Codex Hook events. Each handler is non-blocking and returns `continue: true`; damaged state or unavailable Git must not make Codex unusable.

## Event behavior

- `UserPromptSubmit`: open a private turn journal, record bounded/redacted intent, identify the project, and freeze earlier disk changes.
- `PostToolUse`: record only the completed tool category and changed paths, then attempt a checkpoint.
- `PreCompact`: force a checkpoint and mark the turn compacted.
- `Stop`: force a checkpoint and mark the turn closed without claiming task completion.
- `SessionStart`: freeze current state first, identify an older open turn from another session, write recovery files, and inject a short recovery pointer.

The Hook does not store raw tool input/output. Transcript parsing is best-effort metadata lookup only.

## State locations

Git worktrees use private state keyed by repository and worktree identity under `$CODEX_HOME/continuity`. Non-Git projects use a salted project identity and an external Git directory. Files and directories are written with private permissions where the platform supports them, using atomic replace and process locks.

## Configuration

`$CODEX_HOME/continuity/config.toml` is a strict flat TOML subset. It supports trusted and denied roots, project markers, file/total limits, checkpoint debounce and retention, prompt limit, feedback threshold, log limit, and completion-gate categories.

Invalid configuration falls back to safe defaults with a short diagnostic that does not echo configuration content.

## Trust and duplicate Hooks

Codex discovers plugin Hooks from `hooks/hooks.json`. Use the normal Codex Hook trust prompt or `/hooks` interface. Do not use the dangerous bypass option.

During v1 migration, activate and trust the plugin first. Then run the explicit migration option to remove only the duplicate user-level legacy command. Keep the old script in backup and retain old hidden refs for read-only recovery.
