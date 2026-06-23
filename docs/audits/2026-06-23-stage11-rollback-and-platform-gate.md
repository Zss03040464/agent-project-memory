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

- Python 3.9 and 3.14 each passed 121 tests.
- Package compilation, plugin validation, privacy scan, POSIX shell smoke, real
  Codex plugin/Skill discovery, Hook trust, and full application restart passed.

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

The workflow declares Windows runners for Python 3.9 and 3.14 and executes the
PowerShell smoke script without a skip branch. The branch has not been pushed,
as required, so no remote Windows runner result is claimed. Running that job is
the first publication-time check after explicit push or pull-request authority.

## Gate result

- lifecycle rollback: passed;
- backup integrity and sandbox restore: passed;
- macOS and Linux execution: passed;
- native PowerShell execution: passed;
- public audit path hygiene: passed;
- no push, pull request, merge, tag, or remote-history rewrite: confirmed;
- Windows runner execution: not claimed because publication is prohibited in
  this task.
