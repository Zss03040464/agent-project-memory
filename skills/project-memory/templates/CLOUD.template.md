# Project Memory Cloud Backup

This file records cloud backup locations for the project memory system.

Do not include secrets, access tokens, private keys, or personal account details in this file.

## Cloud root

Example:

```text
CloudDrive/Agent_Project_Memory/
```

Replace this placeholder with the local mounted cloud path or a generic cloud folder reference.

## Recommended cloud structure

```text
Agent_Project_Memory/
  INDEX.md
  CLOUD.md
  records/
  archives/
```

## Recovery workflow

If local memory files or project paths are missing:

1. Read local `project_memory/INDEX.md` if available.
2. Read this `project_memory/CLOUD.md` file.
3. Check the cloud mirror of `INDEX.md`.
4. Check the cloud mirror of the relevant record under `records/`.
5. Check the matching sanitized archive under `archives/`.
6. If no evidence is found, report the missing evidence before creating any replacement project.

## Archive naming convention

```text
<project-slug>_<YYYY-MM>_<status>.zip
```

Examples:

```text
example-web-dashboard_2026-01_stable.zip
example-cli-tool_2026-01_resolved.zip
example-data-pipeline_2026-01_archived.zip
```

## Archive safety rules

Before placing archives in cloud storage, exclude:

- `.env` files
- private keys
- token files
- credential files
- dependency caches
- build outputs
- local virtual environments
- raw personal data
- large generated files that are not needed for recovery

Use `.agent-memory-ignore` as the default archive exclusion list.
