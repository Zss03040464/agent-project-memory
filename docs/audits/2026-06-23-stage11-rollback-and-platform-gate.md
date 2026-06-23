# Stage 11 Rollback and Platform Gate

Date: 2026-06-23 CST

## Transaction rollback rehearsal

The rehearsal used an isolated HOME and CODEX_HOME with pre-existing rules,
config, a v1 Hook, project memory, and continuity state.

The following checks passed:

- install provided the plugin manifest, Skill, CLI, and managed rules;
- v1 migration removed only the duplicate Hook command;
- existing custom memory and continuity files survived install;
- immediate rollback restored every seeded file and directory byte-for-byte and
  restored original modes;
- immediate rollback removed runtime files that did not exist before install;
- default uninstall removed the plugin, CLI, and managed rule block while
  retaining user memory and continuity;
- rollback after uninstall restored the installed plugin, Skill, CLI, rules,
  config, memory, and continuity exactly;
- a synthetic repository retained all hidden refs across lifecycle operations;
- the explicit cleanup path listed refs first and deleted only one selected
  synthetic ref, leaving HEAD, index, worktree, and the legacy ref unchanged.

The phase-0 global backup manifest passed SHA-256 verification. Nine backed-up
files were copied into a sandbox restore root; restored hashes and modes matched
the backup. Live global files were not overwritten during rehearsal.

Real project refs were never deleted. Project memory and continuity remain
archive-by-default data.

## Platform evidence

### macOS

- Python 3.9 and 3.14 each passed 125 tests after the final completion-gate
  regression fixes.
- Package compilation, plugin validation, privacy scan, POSIX shell smoke, real
  Codex plugin/Skill discovery, Hook trust, and full application restart passed.
- The final clean branch passed its own completion gate with all seven required
  evidence categories. Only the expected warnings for optional Chinese project
  management files in this public plugin repository remained.

### Linux

The clean branch archive was streamed to a temporary directory on an Ubuntu
x86_64 host. With Python 3.12 and Codex 0.142.0-alpha.6:

```text
121 tests, 0 failures
compileall passed
privacy scan passed
plugin validation passed
shell smoke: 8 tests, 0 failures
```

The temporary Linux directory and its temporary npm prefix were removed by a
shell trap. No service, firewall, deployment, or persistent server file was
changed.

After the platform-neutral completion-gate policy fix, a fresh archive transfer
was attempted. The SSH endpoint timed out during banner exchange, so no newer
Linux result is claimed. The changed policy and both new regression tests did
pass on the supported Python 3.9 and 3.14 runtimes locally; the earlier Linux
result above remains the latest Linux execution evidence.

### PowerShell and Windows boundary

PowerShell 7.6.3 arm64 ran the native PowerShell smoke workflow in an isolated
Unicode and spaced path:

```text
dry-run passed
install passed
upgrade passed
uninstall passed
managed rules remained idempotent
memory survived default uninstall
```

At the original stage-11 boundary the branch had not been pushed, so no remote
Windows result was claimed. After explicit publication authorization, draft
pull request #1 ran Windows Server 2025 with Python 3.9 and 3.14. Both jobs
passed the platform-aware unit suite, compile, privacy, plugin validation, and
native PowerShell install/upgrade/uninstall smoke workflow.

## Gate result

- lifecycle rollback: passed;
- backup integrity and sandbox restore: passed;
- macOS and Linux execution: passed;
- native PowerShell execution: passed;
- self-hosting completion gate: passed without weakening high-confidence token,
  private-key, authentication-header, sensitive-path, or config-assignment
  blocking;
- unborn-repository completion gate: passed before a project's first normal
  commit and still detected later Git-state changes;
- public audit path hygiene: passed;
- the initial implementation phase performed no push, pull request, merge, tag,
  or remote-history rewrite;
- after later explicit authorization, the feature branch and draft PR #1 were
  published; all Windows, Ubuntu, macOS, and package checks passed;
- no merge, tag, release, branch deletion, or remote-history rewrite occurred.
