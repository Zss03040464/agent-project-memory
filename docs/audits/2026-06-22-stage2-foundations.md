# Stage 2 Foundations Verification

Date: 2026-06-22 CST

Commit range:

```text
254fea6..4319c04
```

## Delivered

- Python package metadata with Python 3.9 minimum support.
- Typed continuity configuration with safe defaults and privacy-safe
  diagnostics.
- Strict, dependency-free TOML subset parsing for the supported flat config
  schema.
- Cross-platform dangerous-root classification with project-marker
  requirements for synchronized storage.
- Sensitive path and text classification, prompt digesting, bounded redaction,
  and digest-only routing.
- Private atomic JSON/text writes, schema-stamped JSON state, damaged-state
  recovery, and process-locked JSONL append.
- POSIX `fcntl` and Windows `msvcrt` lock backends.

## TDD and review history

The initial implementation was followed by repeated specification and quality
reviews. Regression tests were added before each fix for:

- GitHub fine-grained tokens, encrypted and unclosed private keys, and cookie
  assignments;
- synchronized-storage and volume roots;
- Windows end-to-end writes without `os.fchmod`;
- nested private directory permissions and preservation of existing parent
  modes;
- JSONL schema stamping;
- regular-expression performance;
- symbolic-link loops;
- TOML Windows literal strings and relative roots;
- process-lock acquire/unlock failure behavior;
- post-replace success semantics;
- deep-copy recovery defaults.

## Fresh verification

```text
/usr/bin/python3 -m unittest discover -s tests -v
52 tests, 0 failures

/opt/homebrew/bin/python3 -m unittest discover -s tests -v
52 tests, 0 failures

/usr/bin/python3 -m compileall -q src tests
passed

/opt/homebrew/bin/python3 -m compileall -q src tests
passed

python3 scripts/privacy_scan.py
passed

git diff --check
passed
```

Additional main-agent probes:

- adversarial non-secret assignment scan scaled linearly from 8,000 to 32,000
  repeated segments; the 32,000-segment input completed in about 0.037 seconds
  under system Python 3.9;
- unclosed private-key content was removed from the persisted excerpt;
- existing `0755` project parents stayed unchanged while new state paths were
  `0700` and files `0600`;
- missing-state nested defaults were deep copied;
- POSIX and Windows broad roots remained dangerous, while synchronized-storage
  descendants required an actual configured project marker.

## Remaining platform evidence

Windows behavior has unit and simulated `msvcrt` end-to-end coverage, but a
real Windows/PowerShell runner remains required in stage 8. No claim of real
Windows execution is made here.
