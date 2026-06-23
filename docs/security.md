# Security

Agent Project Memory is local-first, fail-open for Codex availability, and fail-closed for publishing sensitive material.

## Never record

- passwords, API keys, access or refresh tokens;
- private or SSH keys;
- authorization headers, cookies, browser profiles, or credential stores;
- `auth.json` or sensitive `.env` content;
- raw tool requests/responses, full process environments, or unfiltered transcript tails;
- real personal data in public examples or test fixtures.

Prompts are byte-bounded and redacted. High-risk prompts retain only a digest. Diagnostics report categories and paths, never matched values.

## Checkpoint boundaries

Automated checkpoints exclude credential filenames, keys, browser state, dependency/cache/build directories, ignored files, nested repositories, oversized files, and content that matches reviewed secret patterns. Symlinks are stored as links without reading external targets. Git LFS paths use the clean filter.

Normal branch, `HEAD`, worktree content, and user staging must remain unchanged. Recovery never automatically checks out a hidden checkpoint.

## Project bootstrap boundaries

Filesystem roots, broad home roots, Downloads roots, Codex state/plugin caches, system directories, broad synchronized roots, symlink escapes, and parents containing nested Git repositories are not automatically initialized or recursively scanned.

Trusted roots still require a dedicated empty directory or a clear project marker. Other non-Git projects use external private checkpoint metadata.

## Installer boundaries

Install, upgrade, and uninstall first snapshot every managed path. Failures restore the previous state. `--backup`/`-Backup` expands the snapshot to include project-memory and continuity data. Existing user records and rules outside the managed block are preserved.

The v1 migration option removes only a legacy command that resolves to the known `git_checkpoint.py`; the script and old refs remain available in backup/read-only form. Plugin activation uses the normal Codex command and trust flow, never the dangerous Hook-trust bypass.

## Scanner coverage

The repository scanner checks text, HTML, JSON, common configuration files, archive member names, bounded archive text, and bounded binary metadata. It never extracts archives and never prints matched values.

Before publishing an archive:

1. apply `.agent-memory-ignore`;
2. inspect the archive listing;
3. run `python3 scripts/privacy_scan.py`;
4. confirm examples contain only fictional placeholders.
