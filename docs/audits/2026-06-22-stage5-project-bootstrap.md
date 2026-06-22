# Stage 5 Project Bootstrap Verification

Date: 2026-06-22 CST

Implementation commit:

```text
329214a feat: bootstrap Git and non-Git projects safely
```

## Behavior

- Existing Git projects use their real repository and are not reinitialized.
- A dedicated marked project or user-created empty directory under a trusted
  root can be initialized automatically.
- Automatic init creates no remote, normal commit, or baseline history.
- A safety `.gitignore` is created only when absent.
- Marked or established non-Git projects that are not safe to initialize use
  external Git metadata under:

```text
$CODEX_HOME/continuity/non_git/<project-id>/git-dir
```

- External project ids use canonical path plus a private installation salt.
- External snapshots use a temporary index, filter sensitive/generated/nested
  content, and never place `.git` in the project directory.
- Hook startup loads continuity config and invokes bootstrap automatically.
- Home, Downloads root, Codex state, broad trusted-root containers, broad
  synchronized storage, parent markers at home scope, nested Git parents, and
  symlink escapes are not automatically initialized or broadly scanned.

## Fresh verification

```text
Python 3.9: 90 tests, 0 failures
Python 3.14: 90 tests, 0 failures
compileall: passed on both runtimes
privacy scan: passed
git diff --check: passed
```

## Current local classification (read-only)

No directories were initialized during this audit.

- existing Git:
  - `/Users/vivian/Workspace/Course/数据库原理/qimo`
  - `/Users/vivian/Workspace/github_code/computer-use-fallback-mac`
  - `/Users/vivian/Workspace/code/agent-project-memory`
- safe auto-init candidates after real installation:
  - `/Users/vivian/Workspace/code/虚拟鼠标`
  - `/Users/vivian/Workspace/code/codex优化`
- external checkpoint candidates:
  - `/Users/vivian/Documents/Codex/2026-06-01/macos26-codex-macos15-macos26-users-vivian`
  - `/Users/vivian/Workspace/code/单子`
  - `/Users/vivian/.gemini/antigravity/mcp/computer-use-fallback-mac`
- excluded:
  - `/Users/vivian/.codex`
  - `/Users/vivian/Downloads/dotfiles`

The classification is a current audit result, not permission to batch mutate
all paths. Real bootstrap remains event-driven and safety checked.
