# Control Loop

The project turns recurring agent work into a small, testable loop.

## Before work: selective feedforward

Load the current project rules, exact matching project memory, current profile, relevant Skill, active continuity state, and recent confirmed corrections. Do not load every project, feedback event, transcript, or Skill body.

Routing returns what was loaded, what was skipped, and why.

## During work: conservative feedback learning

Every correction enters a private event ledger with category, scope, distinct session/turn identity, normalized intent, evidence pointer, and conflict flag.

One correction changes the current task only. Promotion requires at least two distinct turns in the same scope. Any conflicting feedback blocks automatic promotion. The promotion record includes source count and scope, and can be rolled back.

Stable reasons belong in Memory/Profile. Repeatable procedures belong in Skill. Safety/routing invariants may enter concise global rules. Temporary facts stay in project task/handoff files.

## Before delivery: completion gate

The gate checks required evidence, test freshness supplied by the caller, management-file presence, checkpoint coverage supplied by the workflow, sensitive files/content, normal Git state, duplicate-looking outputs, and disclosed limitations.

Hard failures block completion. Warnings remain visible and must be disclosed. Hook diagnostics must never create an endless Stop loop.
