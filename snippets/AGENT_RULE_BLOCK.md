## Project memory and continuity

At task start, load project rules first, then route only the exact current project's memory. Do not inject every INDEX entry, feedback event, transcript, or Skill into context.

For Codex, use the installed `project-memory` Skill and `agent-project-memory` CLI. If continuity reports an interrupted turn, inspect project management files, recovery pointers, current Git/worktree state, and the current worktree's checkpoint before reading any bounded transcript tail. Revalidate external state and update task/handoff files before continuing.

Keep responsibilities separate: Memory stores stable reasons and preferences; Skill stores repeatable procedures; Profile stores current identity and output constraints; project files store current facts and progress; continuity stores in-progress evidence.

Record corrections in the scoped feedback ledger. One occurrence affects the current task only. Promote the same normalized intent only after at least two distinct turns in the same scope and no conflict.

Before claiming completion, run the completion gate. Missing required evidence, sensitive content, or normal Git-state pollution blocks completion. Disclose warnings and unverified items.

Never store credentials, private keys, tokens, cookies, passwords, `auth.json`, sensitive `.env` content, raw tool payloads, or unfiltered archives. Recovery is inspect-first: do not auto-checkout checkpoints, overwrite a worktree, push, or rewrite remote history.
