# Project Summary: Sample Web Dashboard

## Type

project

## Status

active

## Purpose

A fictional dashboard project used to demonstrate how Agent Project Memory records a durable project context.

## Background

The project is a sample web application with a frontend, a small API layer, and documentation. It is not based on a real user project.

## Known paths

```text
Local workspace: <workspace>/sample-web-dashboard
Cloud record: CloudDrive/Agent_Project_Memory/records/sample-web-dashboard/SUMMARY.md
Archive: CloudDrive/Agent_Project_Memory/archives/sample-web-dashboard_2026-01_stable.zip
Git remote: https://github.com/example/sample-web-dashboard.git
```

## Key files

- `README.md`: setup and usage notes
- `src/`: application source code
- `docs/`: architecture and recovery notes

## Environment

- OS: cross-platform placeholder
- Runtime: Node.js placeholder
- Package manager: npm placeholder
- External services: none required for this example

## Important decisions

- Decision: Store recovery records outside the source tree.
  - Reason: The agent can recover context even if the project folder moves.
  - Date: 2026-01-01
- Decision: Keep cloud archives sanitized.
  - Reason: Archives should not contain secrets, dependency caches, or raw personal data.
  - Date: 2026-01-01

## Completed work

- Created initial project layout.
- Added documentation placeholders.
- Recorded cloud mirror and archive naming convention.

## Known issues

- No real issue. This is a sanitized example.

## Do not repeat

- Do not treat `<workspace>/sample-web-dashboard` as a real path.
- Do not create a new empty project if the path is missing; follow the recovery entry point first.
- Do not include `.env`, keys, token files, dependency directories, or build outputs in archives.

## Recovery entry point

If the local path is missing:

1. Read `INDEX.example.md`.
2. Read this record.
3. Search workspace roots for `sample-web-dashboard`.
4. Check the example Git remote placeholder.
5. Check the cloud mirror in `CLOUD.example.md`.
6. Check the sanitized archive name.
7. Report missing evidence before creating any replacement.

## Last reviewed

2026-01-01
