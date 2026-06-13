# Agent Handoff Discipline

## Status

- State: active
- Last updated: 2026-06-14
- Context: Long-running local Agent projects across Codex, Claude Code, Gemini/Antigravity, and related tools.

## Problem

Long-running Agent work often loses state after context compression, tool switching, session restart, or project movement. The user wants Agent behavior to be grounded in durable project files rather than vague memory.

## Durable rules

- Prefer local execution Agent automation over manual user steps when the task can be done through CLI, files, scripts, SSH, API, or browser automation.
- For Agent tasks, provide one complete copyable task block containing target, environment, steps, commands, risks, backup/rollback, verification, and output requirements.
- If the task involves GUI clicking, VNC, browser console, cloud console, or system settings UI, confirm whether Codex with Computer Use is the executor. Non-Codex paths should prefer CLI/API/script/config-file operations.
- When uncertain, start with read-only diagnostics, then branch.
- Do not invent session ids, cache paths, transcript paths, or hidden tool history.

## Required project files for substantial local work

Recommended files:

- `AGENTS.md`
- `AGENT_HANDOFF.md`
- `PROJECT_HISTORY.md`
- `NEXT_AGENT_HANDOFF.md`
- `USER_DIALOGUE.md`
- `.agent_state/current_task.md`
- `.agent_state/last_safe_checkpoint.md`
- `.agent_state/last_dialogue_check.md`
- `logs/agent_sessions/YYYY-MM-DD_HH-mm-summary.md`

## Verification

A handoff is useful only if another Agent can continue from it without reading the full chat history.

## Notes for next agent

When project files and old chat memory conflict, current project files and current user instruction win.
