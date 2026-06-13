# Clone / Dual macOS System Sync

## Status

- State: active
- Last updated: 2026-06-14
- Context: MacBook Air M4 with internal macOS 15 and external macOS 26 system.

## Problem

The user works across more than one macOS system. Agent assumptions about paths, permissions, installed tools, and active system can become wrong after switching between internal and external systems.

## Durable facts

- Internal system: macOS 15.
- External system: macOS 26.
- External volume name used by the user: `Vivian-Banshee`.
- The user treats macOS 26 external system as the main system in current workflows.
- Do not assume macOS 15 and macOS 26 share identical Agent configuration, permissions, tools, or paths.

## Agent rule

Before modifying a project or global Agent config on Mac, identify the active system and path. Do not blindly reuse instructions from the other macOS installation.

## Verification examples

```bash
sw_vers
hostname
pwd
ls -la ~/.codex ~/.claude 2>/dev/null
```

## Notes for next agent

If a path or tool differs between systems, record the actual active path in the project handoff rather than relying on old memory.
