# Project Memory Index

This index maps recurring problems to durable records.

## Records

| Topic | Path | Purpose | Last updated |
|---|---|---|---|
| Dual macOS clone / external system sync | `records/clone-dual-system-sync/SUMMARY.md` | Track macOS internal/external system and clone-related rules | 2026-06-14 |
| Tailscale / Moonlight / Sunshine | `records/tailscale-moonlight-sunshine/SUMMARY.md` | Track remote-control and tailnet networking decisions | 2026-06-14 |
| Claude Code proxy / DP API | `records/claude-code-proxy-fix/SUMMARY.md` | Track Claude Code third-party API and proxy configuration | 2026-06-14 |
| Agent handoff discipline | `records/agent-handoff-discipline/SUMMARY.md` | Track rules for project handoff and continuation | 2026-06-14 |

## Search keywords

- `macOS 15`, `macOS 26`, `external SSD`, `dual system`, `clone`
- `Tailscale`, `Moonlight`, `Sunshine`, `DERP`, `Clash`, `TUN`
- `Claude Code`, `DP API`, `SenseNova`, `DeepSeek`, `ANTHROPIC_BASE_URL`
- `AGENT_HANDOFF`, `PROJECT_HISTORY`, `NEXT_AGENT_HANDOFF`, `USER_DIALOGUE`, `logs/agent_sessions`

## Update protocol

When adding a new record:

1. create `records/<slug>/SUMMARY.md`
2. add one row to this index
3. include verification and rollback if the record describes a system change
4. omit secrets and private identifiers unless necessary and safe
