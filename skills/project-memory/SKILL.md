---
name: project-memory
description: Use when a Codex task may depend on prior project decisions, interrupted work, moved repositories, recurring user corrections, or delivery evidence.
---

# Project Memory

Use exact-project routing and disk evidence to continue work without loading unrelated history.

## Start or recover

1. Read project `AGENTS.md`, `交接.md`, `任务.md`, and `用户.md` in the project-defined order.
2. Run `agent-project-memory route --memory-root "$CODEX_HOME/project_memory" --cwd "$PWD" --json` and load only the exact project match.
3. If continuity reports an interrupted turn, inspect its `recovery.md`, current Git/worktree state, and worktree-specific checkpoint before any transcript tail.
4. Revalidate external services and GUI state; continuity proves saved local evidence, not live external state or unwritten reasoning.
5. Update project management files before resuming costly work.

Do not read every INDEX entry, every feedback event, or a full transcript into the prompt.

## Layers

- Memory: stable reasons, preferences, decisions, and known traps.
- Skill: repeatable workflow, commands, and checklists.
- Profile: current identity and output constraints.
- continuity: in-progress turn journal, checkpoint pointers, and recovery evidence.
- Project files: current facts, plan, status, and handoff.

Route by canonical root and repo/worktree identity. A similar basename is not an exact project match.

## New projects and checkpoints

The Hook classifies the current project automatically. Existing Git repositories keep their normal Git state untouched. Safe dedicated directories may receive `git init`; other non-Git projects use external checkpoint metadata and must not gain a project `.git` directory. Worktree refs, locks, debounce state, and recovery state remain isolated.

## Feedback

Record a correction in the private feedback ledger. Do not promote it after one occurrence. The same normalized intent needs at least 2 distinct sessions or turns in the same scope and no conflict. Promotions retain source count, scope, and rollback evidence; temporary project facts stay in project files.

## Delivery

At task start, save the normal Git baseline with `agent-project-memory snapshot --project-root "$PWD" --output <private-path>`. Before claiming completion, run the `completion gate` through `agent-project-memory gate --baseline <private-path>`, explicitly requiring tests, management-file consistency, checkpoint coverage, and every hard user requirement. Missing evidence, sensitive content, or Git-state pollution is a hard failure. Environment limitations and missing optional management files are warnings to disclose. A Hook may diagnose but must not trap Codex in an endless Stop loop.

## Safety

Never store or print secrets, private keys, tokens, cookies, passwords, `auth.json`, sensitive `.env` content, raw tool responses, or unfiltered archives. Recovery is inspect-first: do not automatically checkout a checkpoint, overwrite a worktree, push, or alter remote history.
