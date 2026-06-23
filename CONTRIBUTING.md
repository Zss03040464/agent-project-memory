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

1. Develop in an isolated branch/worktree and use a failing test before behavior changes.
2. Run `python3 -m unittest discover -s tests -v`.
3. Run `python3 -m compileall -q src scripts tests`.
4. Run `python3 scripts/privacy_scan.py` and `python3 scripts/validate_plugin.py .`.
5. Run `bash scripts/smoke-test.sh` and the PowerShell smoke test on a real PowerShell runtime.
6. Check that examples are fictional and archive listings contain no sensitive files.
7. Keep the managed global rule block concise.
