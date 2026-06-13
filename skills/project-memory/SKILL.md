# Project Memory Skill

## Purpose

This skill gives coding agents a persistent project memory system. It helps agents recover project context, avoid repeated troubleshooting, locate renamed or moved projects, and use cloud backup references before recreating or overwriting missing work.

## When to use

Use this skill before starting:

- project setup
- debugging
- codebase modification
- environment repair
- toolchain configuration
- migration
- synchronization
- long-running user projects
- any task that may depend on previous decisions

## Required first step

Before acting, read the local project memory index:

`project_memory/INDEX.md`

If the current task matches any indexed project or issue, read the linked record under:

`project_memory/records/`

If local paths are missing, do not assume the project is lost. Follow the recovery order in:

`project_memory/CLOUD.md`

## Core rule

A missing local path is not proof that the project is gone. Search local memory, workspace paths, sync folders, Git remotes, and cloud backup references before creating a replacement project.

## Update rule

When a new durable project, solved issue, migration, or important decision is completed, update:

- `project_memory/INDEX.md`
- the relevant file under `project_memory/records/`

If a cloud mirror is configured, update the cloud copy as well.

## Safety rule

Never include secrets, private keys, tokens, personal data, machine-specific private paths, or unfiltered dependency directories in project records or archives.

Use `.agent-memory-ignore` when creating project archives.
