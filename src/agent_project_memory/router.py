"""Small project-memory registry and exact current-project routing."""

from __future__ import annotations

import json
import datetime as dt
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Optional, Tuple

from .identity import GitIdentity, discover_git_identity
from .io import atomic_write_text, write_json_state
from .privacy import scan_sensitive_text


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
    previous_roots: Tuple[str, ...] = ()
    remote_history: Tuple[str, ...] = ()
    worktree_ids: Tuple[str, ...] = ()
    status_entry: Optional[str] = None


@dataclass(frozen=True)
class RouteDecision:
    project_id: Optional[str]
    loaded_records: Tuple[str, ...]
    skipped_records: Tuple[str, ...]
    reason: str
    context: str


def upsert_project_record(memory_root: Path, record: ProjectRecord) -> Path:
    root = Path(memory_root)
    existing = next(
        (
            item
            for item in _load_records(root)
            if item.project_id == record.project_id
        ),
        None,
    )
    if existing is not None:
        record = _merge_record(existing, record)
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
    root = Path(memory_root)
    records = _load_records(root)
    matched: Optional[ProjectRecord] = None
    reason = "matched canonical root"
    for record in records:
        if record.archived:
            continue
        if any(_inside(current, Path(root)) for root in record.canonical_roots):
            matched = record
            break
    identity = discover_git_identity(current)
    if matched is None and identity is not None:
        for record in records:
            if record.archived:
                continue
            if record.repo_id == identity.repo_id or identity.worktree_id in (
                record.worktree_id,
                *record.worktree_ids,
            ):
                matched = _refresh_identity_record(
                    root, record, identity, "repository identity"
                )
                reason = "matched repository identity; record refreshed"
                break
    if matched is None:
        remote = _safe_remote(current)
        if remote:
            for record in records:
                if not record.archived and record.git_remote == remote:
                    if identity is not None:
                        matched = _refresh_identity_record(
                            root, record, identity, "remote identity"
                        )
                    else:
                        matched = record
                    reason = "matched remote identity; record refreshed"
                    break
    skipped = tuple(
        record.project_id
        for record in records
        if matched is None or record.project_id != matched.project_id
    )
    if matched is None:
        return RouteDecision(None, (), skipped, "no exact project match", "")
    if identity is not None and (
        str(identity.worktree_root) not in matched.canonical_roots
        or identity.worktree_id
        not in (matched.worktree_id, *matched.worktree_ids)
    ):
        matched = _refresh_identity_record(root, matched, identity, reason)
        reason = reason + "; worktree identity refreshed"
    remote = _safe_remote(current)
    if remote and remote != matched.git_remote:
        matched = upsert_and_return(
            root,
            replace(
                matched,
                git_remote=remote,
                status_entry="remote identity refreshed",
            ),
        )
        reason = reason + "; remote refreshed"
    stale = _is_stale(matched.last_verified_at)
    if stale:
        reason = reason + "; record stale"
    context = _route_context(root, matched, stale)
    return RouteDecision(
        matched.project_id,
        (matched.project_id,),
        skipped,
        reason,
        context,
    )


def _load_records(root: Path) -> Tuple[ProjectRecord, ...]:
    records = []
    for path in sorted((root / "projects").glob("*/record.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.pop("schema_version", None)
            data["canonical_roots"] = tuple(data["canonical_roots"])
            data["authoritative_files"] = tuple(data["authoritative_files"])
            data["previous_roots"] = tuple(data.get("previous_roots", ()))
            data["remote_history"] = tuple(data.get("remote_history", ()))
            data["worktree_ids"] = tuple(data.get("worktree_ids", ()))
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


def _merge_record(existing: ProjectRecord, incoming: ProjectRecord) -> ProjectRecord:
    roots = tuple(dict.fromkeys(incoming.canonical_roots))
    previous = tuple(
        dict.fromkeys(
            existing.previous_roots
            + tuple(root for root in existing.canonical_roots if root not in roots)
        )
    )
    remote_history = existing.remote_history
    if (
        existing.git_remote
        and incoming.git_remote
        and existing.git_remote != incoming.git_remote
    ):
        remote_history = tuple(
            dict.fromkeys(remote_history + (existing.git_remote,))
        )
    worktree_ids = tuple(
        dict.fromkeys(
            existing.worktree_ids
            + tuple(
                item
                for item in (existing.worktree_id, incoming.worktree_id)
                if item
            )
            + incoming.worktree_ids
        )
    )
    return replace(
        incoming,
        repo_id=incoming.repo_id or existing.repo_id,
        worktree_id=incoming.worktree_id or existing.worktree_id,
        continuity_pointer=(
            incoming.continuity_pointer or existing.continuity_pointer
        ),
        previous_roots=previous,
        remote_history=remote_history,
        worktree_ids=worktree_ids,
        status_entry=incoming.status_entry or existing.status_entry,
    )


def _refresh_identity_record(
    root: Path,
    record: ProjectRecord,
    identity: GitIdentity,
    reason: str,
) -> ProjectRecord:
    active_roots = tuple(
        item for item in record.canonical_roots if Path(item).exists()
    )
    roots = tuple(
        dict.fromkeys(active_roots + (str(identity.worktree_root),))
    )
    previous = tuple(
        dict.fromkeys(
            record.previous_roots
            + tuple(
                item
                for item in record.canonical_roots
                if item not in active_roots
            )
        )
    )
    refreshed = replace(
        record,
        canonical_roots=roots,
        previous_roots=previous,
        repo_id=identity.repo_id,
        worktree_id=identity.worktree_id,
        worktree_ids=tuple(
            dict.fromkeys(
                record.worktree_ids
                + tuple(item for item in (record.worktree_id,) if item)
                + (identity.worktree_id,)
            )
        ),
        last_verified_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        status_entry=reason,
    )
    return upsert_and_return(root, refreshed)


def upsert_and_return(root: Path, record: ProjectRecord) -> ProjectRecord:
    upsert_project_record(root, record)
    return next(
        item for item in _load_records(root) if item.project_id == record.project_id
    )


def _safe_remote(cwd: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(cwd), "remote", "get-url", "origin"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        return None
    remote = result.stdout.decode("utf-8", "replace").strip()
    if not remote or scan_sensitive_text(remote).is_sensitive:
        return None
    return remote


def _is_stale(value: str, days: int = 90) -> bool:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return dt.datetime.now(dt.timezone.utc) - parsed > dt.timedelta(days=days)
    except (TypeError, ValueError):
        return True


def _route_context(
    root: Path, record: ProjectRecord, stale: bool
) -> str:
    parts = [
        "Project: {}\nPurpose: {}\nAuthoritative files: {}\n"
        "Last verified: {}\nContinuity: {}\nStatus: {}".format(
            record.project_id,
            record.purpose,
            ", ".join(record.authoritative_files),
            record.last_verified_at,
            record.continuity_pointer or "none",
            record.status_entry or ("stale; revalidate" if stale else "current"),
        )
    ]
    profile = root / "profile.md"
    try:
        profile_text = profile.read_text(encoding="utf-8")[:2048].strip()
    except OSError:
        profile_text = ""
    if profile_text:
        parts.append("Current profile:\n" + profile_text)
    corrections = _active_corrections(root, record.project_id)
    if corrections:
        parts.append(
            "Recent confirmed corrections:\n"
            + "\n".join("- " + item for item in corrections)
        )
    parts.append("Relevant workflow: use the project-memory Skill.")
    return "\n\n".join(parts)


def _active_corrections(root: Path, project_id: str) -> Tuple[str, ...]:
    found = []
    allowed_scopes = {"global", "project:" + project_id}
    for path in sorted((root / "feedback" / "promotions").glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not value.get("active") or value.get("scope") not in allowed_scopes:
            continue
        intent = value.get("normalized_intent")
        if isinstance(intent, str) and intent:
            found.append(intent)
        if len(found) >= 5:
            break
    return tuple(found)
