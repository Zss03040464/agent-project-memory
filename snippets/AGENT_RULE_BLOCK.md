## Project memory, history index, and recovery workflow

Before starting any project setup, debugging, code modification, migration, synchronization, environment repair, backup restoration, or long-running task, read the local project memory index:

`project_memory/INDEX.md`

If the current task is related to an indexed project or solved issue, read the linked record under:

`project_memory/records/`

If a local project path, memory file, or record is missing, damaged, or incomplete, do not assume that the project is gone. Read:

`project_memory/CLOUD.md`

Then follow this recovery order:

1. Search the current local workspace for the same or similar project name.
2. Check known synchronized folders.
3. Check Git remotes recorded in the project record.
4. Check the cloud memory mirror recorded in `CLOUD.md`.
5. Check sanitized cloud archives recorded in `CLOUD.md`.
6. If the project still cannot be found, report the missing evidence clearly before creating any replacement.

A missing local path is not proof that a project is gone. Never create, overwrite, or replace a project until the memory index, project record, workspace, sync locations, Git remotes, and cloud backup references have been checked.

After completing a new long-running project, solving a complex issue, completing a migration, or making an important project decision, update `project_memory/INDEX.md` and create or update the corresponding record under `project_memory/records/`.

Never store API keys, private keys, tokens, passwords, credential files, raw personal data, or unfiltered archive contents in project memory. Use `.agent-memory-ignore` before creating any archive.
