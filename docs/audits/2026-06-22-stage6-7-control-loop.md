# Stage 6–7 Routing and Control Loop Verification

Date: 2026-06-22 CST

Implementation commit: `f91b9be`

- Project records use exact canonical-root routing and return a testable reason.
- `INDEX.md` is only a compact pointer table; unmatched records are not loaded.
- Records separate project purpose/constraints from current continuity pointers.
- Feedback is appended to a private event ledger.
- Promotion requires the same normalized intent from at least two distinct
  session/turn pairs in the same scope and no conflict.
- Project scopes are isolated; promotion metadata and rollback are retained.
- Completion gate hard-fails missing requirement evidence, sensitive content,
  and unexpected Git state changes. Missing management files and
  duplicate-looking outputs are warnings.

Fresh verification: Python 3.9 and 3.14 each passed 94 tests; compile, privacy
scan, and diff checks passed.
