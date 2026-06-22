# Agent Project Memory Development Rules

## Scope

This repository provides a cross-platform Markdown project-memory system plus
Codex continuity hooks, skills, plugin packaging, installers, recovery tools,
and delivery checks.

## Required workflow

- Develop only on an isolated feature branch/worktree, never directly on `main`.
- Use test-driven development for behavior changes: add a failing test, confirm
  the expected failure, implement the minimum fix, then rerun the focused and
  full suites.
- Investigate failures to root cause before changing production code.
- Keep Python hook runtime dependencies in the standard library unless a
  dependency is strictly limited to development or testing.
- Create clear local commits at verified phase boundaries.
- Do not push, open pull requests, merge, tag, or rewrite remote history unless
  the user explicitly authorizes publication.

## Safety

- Never read, print, copy, log, fixture, or commit real credentials, tokens,
  cookies, private keys, `auth.json`, or sensitive `.env` values.
- Hook and checkpoint code must fail open: diagnostics may be emitted, but
  Codex must not be made unusable by damaged state or unavailable tooling.
- Automated checkpoints must not modify the user's normal branch, `HEAD`,
  working tree, or index.
- Recovery is inspect-first. Never auto-checkout or overwrite the working tree.
- Dangerous roots such as filesystem roots, home roots, Downloads roots,
  Codex state, plugin caches, and broad sync roots must not be auto-initialized
  or recursively scanned.

## Verification

- Run the focused test during each red/green cycle.
- Before a phase commit, run all tests relevant to that phase plus privacy and
  manifest checks.
- Before delivery, run the complete unit, integration, installer, plugin,
  recovery, worktree-isolation, privacy, and completion-gate matrix.
- PowerShell behavior must be verified on a real Windows/PowerShell runner; a
  skipped test is not a pass.

## Compatibility

- Preserve the repository's portable Markdown records and non-Codex installers.
- Keep public examples fictional and free of machine-specific private paths.
- Maintain read-only compatibility with legacy v1 checkpoint refs; do not
  delete them automatically.
