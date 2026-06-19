# Security

Agent Project Memory is designed to avoid exposing private information.

## Do not store

Never store these in public records, examples, or cloud archives:

- passwords
- API keys
- access tokens
- refresh tokens
- private keys
- SSH keys
- cookie jars
- browser profiles
- credential JSON files
- raw personal data
- private account identifiers
- sensitive machine-specific paths in public examples

## Public examples

Public examples must use fictional names only.

Use placeholders such as:

```text
<workspace>/example-project
CloudDrive/Agent_Project_Memory/
https://github.com/example/example-project.git
```

Do not use real user names, real emails, real device names, private repository names, or private project names.

## Installer safety

Installers must be idempotent. They must not duplicate the managed rule block, and they must not overwrite user `INDEX.md` or `CLOUD.md` by default.

Any modification to an existing rules file is backed up first. Template overwrites require `--force-template` or `-ForceTemplate` and also create backups.

## Archive safety

Before uploading archives to any cloud service:

1. Use `.agent-memory-ignore`.
2. Inspect the archive file list.
3. Confirm that no secrets or personal files are included.
4. Prefer source files and documentation over raw machine state.

## Default exclusions

The default ignore file excludes common secret files, dependency directories, build outputs, caches, and large generated files.

Review it before every archive operation.
