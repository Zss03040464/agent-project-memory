# Cloud Drive Backup

This document describes a safe cloud backup layout. It uses generic cloud drive language and does not require a specific provider.

## Recommended folder

```text
Agent_Project_Memory/
  INDEX.md
  CLOUD.md
  records/
  archives/
```

## What to sync

Safe to sync after review:

- `INDEX.md`
- `CLOUD.md`
- `records/`
- sanitized archives
- templates

Do not sync without review:

- raw project directories
- credential files
- token files
- private keys
- local database dumps
- browser profiles
- unfiltered dependency folders

## Archive workflow

1. Review `.agent-memory-ignore`.
2. Create an archive that excludes sensitive files and unnecessary generated files.
3. Inspect the archive file list.
4. Place the archive under `Agent_Project_Memory/archives/`.
5. Update the relevant project record with the archive name and date.

## Restore workflow

1. Read the local index.
2. Read the project record.
3. Check the cloud mirror.
4. Download the matching sanitized archive only if needed.
5. Extract to a safe temporary directory first.
6. Inspect the contents before replacing any local project folder.
