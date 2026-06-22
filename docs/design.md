# Design

Agent Project Memory combines a portable Markdown registry with Codex continuity primitives. The design keeps durable evidence small, local, inspectable, and scoped to one project or worktree.

## Layers

1. **Project evidence**: project rules, task status, handoff, and files on disk.
2. **Continuity**: a private turn journal, recovery report, and checkpoint pointers.
3. **Project memory**: a compact index and exact-project records.
4. **Skill**: repeatable recovery, routing, feedback, and delivery workflows.
5. **Profile**: current identity and output constraints supplied by the active session.
6. **Control loop**: selective pre-task loading, evidence-counted feedback promotion, and a completion gate.

The layers are deliberately separate. Memory does not replace project facts, Skill does not store every project, and continuity does not claim to preserve unwritten model state.

## Identity and routing

A Git repository identity is derived from its canonical common Git directory. A worktree identity is derived from canonical worktree root plus worktree Git directory. Branch names and directory basenames are not identities.

Project memory routing uses canonical roots and stored repository/worktree metadata. `INDEX.md` remains a small pointer table. Only an exact current-project match contributes context; unrelated records are skipped with an explainable routing decision.

## Checkpoints

Git checkpoints use a temporary index and hidden refs:

```text
refs/codex/checkpoints/worktrees/<worktree-id>/latest
refs/codex/checkpoints/worktrees/<worktree-id>/history/<timestamp>-<tree>
```

Lock, debounce, and state files are worktree-specific. Legacy v1 refs remain read-only. Sensitive, ignored, generated, nested-repository, oversized, and unsafe paths are filtered. A tracked sensitive change retains the committed version instead of copying the sensitive working-tree content.

For non-Git projects that must not receive `.git`, an external Git directory and temporary index live under private continuity state. Safe dedicated directories under configured trusted roots may be initialized without creating a commit or remote.

## Turn journal

The journal has `open`, `compacted`, `closed`, `interrupted`, and `recovered` states. Events are combined because no single Hook event is guaranteed to cover every failure:

- prompt submission opens or updates a turn;
- completed tool use updates bounded evidence and attempts a checkpoint;
- pre-compaction and stop force checkpoints;
- session start freezes current disk state before classifying an older open turn as interrupted.

Recovery files contain redacted, bounded metadata and pointers. Raw tool payloads and full transcript tails are not copied.

## Feedback and delivery

Feedback is scoped by category, project/global scope, normalized intent, and distinct session/turn evidence. Promotion requires at least two distinct pieces of evidence and no conflict. Promotions and rollbacks remain traceable in the private ledger.

The completion gate separates hard failures from warnings. Missing required evidence, sensitive content, and normal Git-state pollution are hard failures. Optional environment limitations and missing management documents are warnings that must be disclosed.

## Distribution

The Codex plugin uses default discovery:

- `.codex-plugin/plugin.json` for plugin metadata;
- `hooks/hooks.json` for Hooks;
- `skills/project-memory/SKILL.md` for the Skill;
- `scripts/hook-entry.py` and bundled `src/` for dependency-free Hook execution.

The manifest intentionally omits an unsupported top-level `hooks` field. Shell and PowerShell entrypoints call one transactional Python installer, so lifecycle behavior is consistent across platforms.
