# Contributing

Contributions are welcome.

## Privacy requirement

Do not submit examples containing real personal information, private project names, private repository names, machine-specific paths, email addresses, tokens, keys, or credentials.

All examples must use fictional placeholders.

## Good contributions

- new agent installation snippets
- better recovery workflow documentation
- safer archive ignore patterns
- additional templates
- validation scripts
- documentation improvements

## Before opening a pull request

1. Run `bash scripts/smoke-test.sh`.
2. If PowerShell is available, run `pwsh -NoProfile -File scripts/smoke-test.ps1`.
3. Run a local search for secrets and private identifiers.
4. Check that examples are fictional.
5. Confirm that no archive contains sensitive files.
6. Keep the global rule block concise.
