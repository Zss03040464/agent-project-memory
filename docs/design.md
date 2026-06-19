# Design

Agent Project Memory uses a local-first registry pattern.

## Components

### `INDEX.md`

A short, searchable registry of known projects, solved issues, workflows, migrations, and durable decisions.

It should stay brief. Each entry links to a record.

### `records/`

Detailed project or issue records. Records contain enough context for an agent to continue work without repeating solved troubleshooting.

### `CLOUD.md`

Cloud backup and recovery references. This file does not upload anything by itself. It tells an agent where to look if local files or paths are missing.

### `archives/`

Optional location for sanitized full project archives. Archives are for recovery, not for routine context reading.

### managed global rule block

The installer can insert a managed Markdown block into an existing global rules file. The block is bounded by `BEGIN AGENT_PROJECT_MEMORY_RULES` and `END AGENT_PROJECT_MEMORY_RULES`, so repeated installation can replace the block instead of appending duplicates.

## Why not put everything in one global rules file?

Large global rule files are harder to maintain and harder for agents to scan accurately. A small index plus linked records keeps the global rules stable while allowing the memory system to grow.

## Why local-first?

Local files are transparent, easy to inspect, easy to version, and supported by most coding agents.

## Why cloud references?

Cloud storage adds a recovery layer when local folders are renamed, moved, damaged, or missing.

## Why not automatic upload by default?

Automatic upload can accidentally expose secrets or private data. This project intentionally starts with explicit records and safety-first archive rules.
