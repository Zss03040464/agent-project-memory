# Tailscale / Moonlight / Sunshine

## Status

- State: active
- Last updated: 2026-06-14
- Context: Mac client, Windows host, Tailscale, Sunshine/Moonlight remote control.

## Problem

Remote-control quality depends on Tailscale route behavior, Clash/TUN routing, DERP fallback, and Sunshine/Moonlight service state. Old fixes can be forgotten when switching Agent sessions.

## Durable facts

- Windows host uses Sunshine.
- Mac uses Moonlight client.
- Tailscale is used for cross-device access.
- The user keeps Clash system proxy and TUN enabled on Mac.
- Tailscale traffic should not be forced through the wrong physical interface by proxy/TUN configuration.

## Known fix pattern

When Tailscale access works only after changing interface behavior, check Clash/mihomo TUN settings and direct routing for `100.64.0.0/10`.

Relevant durable rule:

```yaml
tun:
  auto-detect-interface: false
  route-exclude-address:
    - 100.64.0.0/10
```

Also ensure DIRECT rules cover Tailscale control and tailnet traffic where appropriate.

## Verification examples

```bash
tailscale status
tailscale netcheck
ping <windows-tailscale-ip>
```

## Notes for next agent

Do not ask the user to turn off system proxy or TUN as the first solution. The user's intended baseline is proxy and TUN enabled.
