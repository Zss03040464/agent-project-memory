"""Small project-memory registry and exact current-project routing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Tuple

from .io import atomic_write_text, write_json_state


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    canonical_roots: Tuple[str, ...]
    purpose: str
    authoritative_files: Tuple[str, ...]
    last_verified_at: str
    git_remote: Optional[str] = None
    default_branch: Optional[str] = None
    repo_id: Optional[str] = None
    worktree_id: Optional[str] = None
    continuity_pointer: Optional[str] = None
    archived: bool = False


@dataclass(frozen=True)
class RouteDecision:
    project_id: Optional[str]
    loaded_records: Tuple[str, ...]
    skipped_records: Tuple[str, ...]
    reason: str
    context: str


def upsert_project_record(memory_root: Path, record: ProjectRecord) -> Path:
    root = Path(memory_root)
    path = root / "projects" / record.project_id / "record.json"
    write_json_state(path, asdict(record), schema_version=1)
    summary = root / "projects" / record.project_id / "SUMMARY.md"
    atomic_write_text(
        summary,
        "# Project Summary: {}\n\n"
        "Purpose: {}\n\n"
        "Canonical roots:\n{}\n\n"
        "Authoritative files: {}\n\n"
        "Last verified: {}\n".format(
            record.project_id,
            record.purpose,
            "\n".join("- `{}`".format(item) for item in record.canonical_roots),
            ", ".join(record.authoritative_files),
            record.last_verified_at,
        ),
    )
    _rebuild_index(root)
    return path


def route_project_memory(cwd: Path, memory_root: Path) -> RouteDecision:
    current = Path(cwd).resolve()
    records = _load_records(Path(memory_root))
    matched: Optional[ProjectRecord] = None
    for record in records:
        if record.archived:
            continue
        if any(_inside(current, Path(root)) for root in record.canonical_roots):
            matched = record
            break
    skipped = tuple(
        record.project_id
        for record in records
        if matched is None or record.project_id != matched.project_id
    )
    if matched is None:
        return RouteDecision(None, (), skipped, "no exact project match", "")
    return RouteDecision(
        matched.project_id,
        (matched.project_id,),
        skipped,
        "matched canonical root",
        "Project: {}\nPurpose: {}\nAuthoritative files: {}\n"
        "Last verified: {}\nContinuity: {}".format(
            matched.project_id,
            matched.purpose,
            ", ".join(matched.authoritative_files),
            matched.last_verified_at,
            matched.continuity_pointer or "none",
        ),
    )


def _load_records(root: Path) -> Tuple[ProjectRecord, ...]:
    records = []
    for path in sorted((root / "projects").glob("*/record.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("schema_version", None)
            data["canonical_roots"] = tuple(data["canonical_roots"])
            data["authoritative_files"] = tuple(data["authoritative_files"])
            records.append(ProjectRecord(**data))
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return tuple(records)


def _rebuild_index(root: Path) -> None:
    lines = [
        "# Project Memory Index",
        "",
        "Small routing table only. Load a project record only after an exact match.",
        "",
    ]
    for record in _load_records(root):
        lines.append(
            "- `{}` → `projects/{}/SUMMARY.md` [{}]".format(
                record.project_id,
                record.project_id,
                "archived" if record.archived else "active",
            )
        )
    lines.append("")
    atomic_write_text(root / "INDEX.md", "\n".join(lines))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False
