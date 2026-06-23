"""Dependency-free command line interface for routing, feedback, and gates."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from .completion_gate import capture_git_state, run_completion_gate
from .feedback import record_feedback, rollback_promotion
from .io import write_json_state
from .router import ProjectRecord, route_project_memory, upsert_project_record


def _print(value: Any, as_json: bool) -> None:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    else:
        if isinstance(value, dict):
            for key, item in value.items():
                print("{}: {}".format(key, item))
        else:
            print(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-project-memory")
    commands = parser.add_subparsers(dest="command", required=True)

    route = commands.add_parser("route", help="Route only exact current-project memory")
    route.add_argument("--memory-root", required=True, type=Path)
    route.add_argument("--cwd", required=True, type=Path)
    route.add_argument("--json", action="store_true")

    project = commands.add_parser("project", help="Manage project records")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    upsert = project_commands.add_parser("upsert")
    upsert.add_argument("--memory-root", required=True, type=Path)
    upsert.add_argument("--project-id", required=True)
    upsert.add_argument("--root", action="append", required=True)
    upsert.add_argument("--purpose", required=True)
    upsert.add_argument("--authoritative-file", action="append", default=[])
    upsert.add_argument("--verified-at", required=True)
    upsert.add_argument("--git-remote")
    upsert.add_argument("--default-branch")
    upsert.add_argument("--repo-id")
    upsert.add_argument("--worktree-id")
    upsert.add_argument("--continuity-pointer")
    upsert.add_argument("--json", action="store_true")

    feedback = commands.add_parser("feedback", help="Record or roll back feedback")
    feedback_commands = feedback.add_subparsers(dest="feedback_command", required=True)
    record = feedback_commands.add_parser("record")
    record.add_argument("--root", required=True, type=Path)
    record.add_argument("--category", required=True)
    record.add_argument("--scope", required=True)
    record.add_argument("--session-id", required=True)
    record.add_argument("--turn-id", required=True)
    record.add_argument("--intent", required=True)
    record.add_argument("--evidence", required=True)
    record.add_argument("--conflict", action="store_true")
    record.add_argument("--threshold", type=int, default=2)
    record.add_argument("--json", action="store_true")
    rollback = feedback_commands.add_parser("rollback")
    rollback.add_argument("--root", required=True, type=Path)
    rollback.add_argument("--rule-id", required=True)
    rollback.add_argument("--reason", required=True)

    snapshot = commands.add_parser("snapshot", help="Save a Git-state delivery baseline")
    snapshot.add_argument("--project-root", required=True, type=Path)
    snapshot.add_argument("--output", required=True, type=Path)

    gate = commands.add_parser("gate", help="Run the evidence completion gate")
    gate.add_argument("--project-root", required=True, type=Path)
    gate.add_argument("--require", action="append", default=[])
    gate.add_argument("--evidence", action="append", default=[])
    gate.add_argument("--baseline", type=Path)
    gate.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "route":
        _print(route_project_memory(args.cwd, args.memory_root), args.json)
        return 0
    if args.command == "project":
        record = ProjectRecord(
            project_id=args.project_id,
            canonical_roots=tuple(str(Path(item).resolve()) for item in args.root),
            purpose=args.purpose,
            authoritative_files=tuple(args.authoritative_file),
            last_verified_at=args.verified_at,
            git_remote=args.git_remote,
            default_branch=args.default_branch,
            repo_id=args.repo_id,
            worktree_id=args.worktree_id,
            continuity_pointer=args.continuity_pointer,
        )
        path = upsert_project_record(args.memory_root, record)
        _print({"record": str(path)}, args.json)
        return 0
    if args.command == "feedback":
        if args.feedback_command == "rollback":
            rollback_promotion(args.root, args.rule_id, reason=args.reason)
            return 0
        decision = record_feedback(
            args.root,
            category=args.category,
            scope=args.scope,
            session_id=args.session_id,
            turn_id=args.turn_id,
            normalized_intent=args.intent,
            evidence_pointer=args.evidence,
            conflict=args.conflict,
            threshold=args.threshold,
        )
        _print(decision, args.json)
        return 0
    if args.command == "snapshot":
        state = capture_git_state(args.project_root)
        if state is None:
            print("Git state is unavailable")
            return 2
        write_json_state(
            args.output,
            {"git_state": list(state)},
            schema_version=1,
        )
        return 0
    evidence = {name: True for name in args.evidence}
    expected = _load_baseline(args.baseline) if args.baseline else capture_git_state(args.project_root)
    result = run_completion_gate(
        args.project_root,
        required_requirements=tuple(args.require),
        evidence=evidence,
        expected_git_state=expected,
    )
    _print(result, args.json)
    return 0 if result.passed else 2


def _load_baseline(path: Path) -> Optional[Tuple[str, str, str, str]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        state = data.get("git_state")
        if not isinstance(state, list) or len(state) != 4:
            return None
        return tuple(str(item) for item in state)  # type: ignore[return-value]
    except (OSError, ValueError, TypeError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
