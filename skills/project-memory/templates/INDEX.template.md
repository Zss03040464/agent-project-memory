# Project Memory Index

This file is the high-level registry for projects, solved issues, migrations, workflows, and durable decisions that an agent may need to remember.

Before acting on a project or troubleshooting task, read this file and check whether the current task is related to an existing record.

## Records

### Example Project Registry

- Type: project
- Status: active
- Keywords: example, registry, placeholder
- Record: `records/example-project/SUMMARY.md`
- Cloud mirror: see `CLOUD.md`

### Example Environment Issue

- Type: issue
- Status: resolved
- Keywords: environment, proxy, placeholder
- Record: `records/example-environment-issue/SUMMARY.md`
- Cloud mirror: see `CLOUD.md`

## Status values

Use one of:

- active
- paused
- resolved
- archived
- deprecated
- unknown

## Type values

Use one of:

- project
- issue
- migration
- configuration
- workflow
- decision
- archive

## Maintenance rules

When a new durable project, solved issue, migration, or important decision is created, add one concise entry here.

Each entry must link to a corresponding record under `records/`.

Keep this file brief. Store details in the linked record.
