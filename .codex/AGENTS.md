# Global Agent Project Memory Rules

## 1. Purpose

This file defines how local execution agents should use persistent project memory.

Agents must not rely only on hidden chat context, compressed summaries, IDE cache, or tool-specific session memory when doing non-trivial project work.

## 2. Required reading order

Before starting or resuming project work, read in this order when the files exist:

1. project-level `AGENTS.md`
2. `.codex/project_memory/INDEX.md`
3. the relevant `.codex/project_memory/records/<topic>/SUMMARY.md`
4. project `AGENT_HANDOFF.md`
5. latest `logs/agent_sessions/*`
6. task-specific README, setup, or test files

Do not guess from old chat memory when project files exist.

## 3. What must be recorded

For each non-trivial task, preserve enough information for a new agent to continue without asking the user to repeat context:

- problem name
- affected machine, OS, tool, service, or project
- root cause or current best hypothesis
- exact files changed
- exact commands used, if safe to store
- verification evidence
- rollback path
- remaining work
- user decisions and constraints

## 4. What must not be recorded

Never store secrets, private keys, API keys, tokens, cookies, passwords, private order data, raw screenshots containing private information, or full sensitive logs.

Use placeholders such as:

`[REDACTED: credential or private data]`

## 5. Update rule

When a task changes durable project knowledge, update both:

- `.codex/project_memory/INDEX.md`
- the relevant `.codex/project_memory/records/<topic>/SUMMARY.md`

If the topic does not exist, create a new directory under `records/` using a short lowercase slug.

## 6. Conflict rule

When records conflict:

1. current explicit user instruction wins
2. newer project file wins over older project file
3. project-local files win over global memory
4. old chat memory is lowest priority

State the conflict instead of silently merging incompatible instructions.

## 7. Completion rule

A non-trivial task is not complete until verification and memory update are complete, unless the user explicitly says not to write files.
