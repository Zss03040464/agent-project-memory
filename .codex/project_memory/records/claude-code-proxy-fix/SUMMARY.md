# Claude Code Proxy / DP API

## Status

- State: active
- Last updated: 2026-06-14
- Context: Claude Code using third-party DP/SenseNova-compatible API and local proxy environment.

## Problem

Claude Code API configuration can drift after key rotation, version change, or proxy change. The user expects direct terminal-ready configuration instructions for DP API key switching, not a generic Agent handoff, when asking for that specific task.

## Durable facts

- DP/SenseNova base URL used in prior configuration: `https://token.sensenova.cn`.
- Typical model names used by the user include `deepseek-v4-flash` and `sensenova-6.7-flash-lite`.
- User preference for the DP key switch request: provide a direct terminal command block, not a local Agent task template.

## Safe storage rule

Do not store API keys in memory files. Use placeholders only.

```text
ANTHROPIC_AUTH_TOKEN=[REDACTED: DP API key]
```

## Verification examples

```bash
claude --version
cat ~/.claude/settings.json
printenv | grep -E 'ANTHROPIC|DISABLE'
```

## Notes for next agent

If the user asks generally about configuring Claude Code or debugging a project, a handoff may be appropriate. If the user asks specifically to switch Claude DP API key, provide the direct command pattern.
