"""Persistent turn journal and abnormal interruption recovery."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .checkpoint import (
    CheckpointResult,
    changed_worktree_paths,
    checkpoint_refs,
    create_git_checkpoint,
)
from .identity import GitIdentity, discover_git_identity
from .io import (
    append_jsonl,
    ensure_private_directory,
    process_lock,
    read_json_state,
    write_json_state,
)
from .privacy import is_digest_only, summarize_prompt
from .recovery import write_recovery_artifacts


TURN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ContinuityResult:
    event: str
    turn_path: Optional[Path]
    events_path: Optional[Path]
    recovery_json: Optional[Path] = None
    recovery_markdown: Optional[Path] = None
    additional_context: str = ""


def handle_hook_event(
    payload: Mapping[str, Any], *, codex_home: Path
) -> ContinuityResult:
    """Apply one official Codex Hook event to persistent state."""

    event = str(payload.get("hook_event_name") or "")
    cwd = Path(str(payload.get("cwd") or "."))
    identity = discover_git_identity(cwd)
    if identity is None:
        return ContinuityResult(event, None, None)
    state_dir = continuity_state_dir(Path(codex_home), identity)
    turn_path = state_dir / "turn.json"
    events_path = state_dir / "events.jsonl"
    with process_lock(state_dir / "turn.lock"):
        if event == "SessionStart":
            return _handle_session_start(
                payload,
                identity,
                state_dir,
                turn_path,
                events_path,
            )
        existing = _load_turn(turn_path, identity)
        checkpoint = _safe_checkpoint(identity, event)
        if event == "UserPromptSubmit":
            state = _open_turn(payload, identity, checkpoint)
        else:
            state = existing
            _refresh_common_state(state, payload, identity, checkpoint, event)
            if event == "PostToolUse":
                state["status"] = state.get("status") or "open"
                state["last_completed_tool"] = _tool_category(
                    str(payload.get("tool_name") or "")
                )
            elif event == "PreCompact":
                state["status"] = "compacted"
                state["closed_at"] = None
            elif event == "Stop":
                state["status"] = "closed"
                state["closed_at"] = _now()
        _persist_turn(turn_path, events_path, state, event)
        return ContinuityResult(event, turn_path, events_path)


def continuity_state_dir(codex_home: Path, identity: GitIdentity) -> Path:
    return ensure_private_directory(
        Path(codex_home)
        / "continuity"
        / "repos"
        / identity.repo_id
        / "worktrees"
        / identity.worktree_id
    )


def mark_recovered(turn_path: Path) -> None:
    target = Path(turn_path)
    state_dir = target.parent
    with process_lock(state_dir / "turn.lock"):
        result = read_json_state(
            target,
            schema_version=TURN_SCHEMA_VERSION,
            default={},
        )
        state = result.data
        state["status"] = "recovered"
        state["updated_at"] = _now()
        state["last_event"] = "Recovered"
        write_json_state(
            target, state, schema_version=TURN_SCHEMA_VERSION
        )
        append_jsonl(
            state_dir / "events.jsonl",
            {
                "event": "Recovered",
                "status": "recovered",
                "session_id": state.get("session_id"),
                "turn_id": state.get("turn_id"),
                "timestamp": state["updated_at"],
            },
        )


def _handle_session_start(
    payload: Mapping[str, Any],
    identity: GitIdentity,
    state_dir: Path,
    turn_path: Path,
    events_path: Path,
) -> ContinuityResult:
    checkpoint = _safe_checkpoint(identity, "SessionStart")
    state = _load_turn(turn_path, identity)
    new_session = str(payload.get("session_id") or "")
    previous_session = state.get("session_id")
    if (
        state.get("status") in {"open", "compacted"}
        and isinstance(previous_session, str)
        and previous_session
        and previous_session != new_session
    ):
        _refresh_common_state(
            state, payload, identity, checkpoint, "SessionStart"
        )
        state["status"] = "interrupted"
        state["interrupted_at"] = _now()
        _persist_turn(turn_path, events_path, state, "SessionStart")
        recovery_json, recovery_markdown, context = write_recovery_artifacts(
            state_dir, turn=state, new_session_id=new_session
        )
        return ContinuityResult(
            "SessionStart",
            turn_path,
            events_path,
            recovery_json,
            recovery_markdown,
            context,
        )
    return ContinuityResult("SessionStart", turn_path, events_path)


def _open_turn(
    payload: Mapping[str, Any],
    identity: GitIdentity,
    checkpoint: CheckpointResult,
) -> Dict[str, Any]:
    prompt = str(payload.get("prompt") or "")
    summary = summarize_prompt(prompt, max_bytes=8 * 1024)
    opened = _now()
    state: Dict[str, Any] = {
        "session_id": str(payload.get("session_id") or ""),
        "turn_id": (
            str(payload.get("turn_id"))
            if payload.get("turn_id") is not None
            else None
        ),
        "transcript_path": (
            str(payload.get("transcript_path"))
            if payload.get("transcript_path")
            else None
        ),
        "project_root": str(identity.worktree_root),
        "repo_id": identity.repo_id,
        "worktree_id": identity.worktree_id,
        "git_head": identity.head,
        "branch": identity.branch,
        "status": "open",
        "opened_at": opened,
        "updated_at": opened,
        "closed_at": None,
        "prompt_digest": summary.digest,
        "prompt_excerpt_redacted": (
            None if is_digest_only(text=prompt) else summary.excerpt
        ),
        "last_completed_tool": None,
        "last_event": "UserPromptSubmit",
        "changed_paths": list(
            changed_worktree_paths(identity.worktree_root)
        ),
        "checkpoint_ref": checkpoint.latest_ref,
        "checkpoint_commit": checkpoint.commit,
        "requires_external_revalidation": True,
    }
    return state


def _load_turn(turn_path: Path, identity: GitIdentity) -> Dict[str, Any]:
    result = read_json_state(
        turn_path,
        schema_version=TURN_SCHEMA_VERSION,
        default={
            "session_id": None,
            "turn_id": None,
            "transcript_path": None,
            "project_root": str(identity.worktree_root),
            "repo_id": identity.repo_id,
            "worktree_id": identity.worktree_id,
            "git_head": identity.head,
            "branch": identity.branch,
            "status": None,
            "opened_at": None,
            "updated_at": None,
            "closed_at": None,
            "prompt_digest": None,
            "prompt_excerpt_redacted": None,
            "last_completed_tool": None,
            "last_event": None,
            "changed_paths": [],
            "checkpoint_ref": None,
            "checkpoint_commit": None,
            "requires_external_revalidation": True,
        },
    )
    return result.data


def _refresh_common_state(
    state: Dict[str, Any],
    payload: Mapping[str, Any],
    identity: GitIdentity,
    checkpoint: CheckpointResult,
    event: str,
) -> None:
    state["project_root"] = str(identity.worktree_root)
    state["repo_id"] = identity.repo_id
    state["worktree_id"] = identity.worktree_id
    state["git_head"] = identity.head
    state["branch"] = identity.branch
    state["updated_at"] = _now()
    state["last_event"] = event
    state["changed_paths"] = list(
        changed_worktree_paths(identity.worktree_root)
    )
    state["requires_external_revalidation"] = True
    if payload.get("transcript_path"):
        state["transcript_path"] = str(payload["transcript_path"])
    if checkpoint.latest_ref:
        state["checkpoint_ref"] = checkpoint.latest_ref
    if checkpoint.commit:
        state["checkpoint_commit"] = checkpoint.commit


def _persist_turn(
    turn_path: Path,
    events_path: Path,
    state: Mapping[str, Any],
    event: str,
) -> None:
    write_json_state(
        turn_path, state, schema_version=TURN_SCHEMA_VERSION
    )
    append_jsonl(
        events_path,
        {
            "event": event,
            "status": state.get("status"),
            "session_id": state.get("session_id"),
            "turn_id": state.get("turn_id"),
            "timestamp": state.get("updated_at") or _now(),
            "checkpoint_commit": state.get("checkpoint_commit"),
        },
    )


def _tool_category(tool_name: str) -> str:
    folded = tool_name.casefold()
    if any(token in folded for token in ("exec", "shell", "bash", "command")):
        return "shell"
    if any(token in folded for token in ("apply_patch", "edit", "write")):
        return "file_write"
    if any(
        token in folded
        for token in ("browser", "computer", "mcp", "web", "chrome")
    ):
        return "external_tool"
    return "tool"


def _safe_checkpoint(identity: GitIdentity, event: str) -> CheckpointResult:
    try:
        return create_git_checkpoint(identity.worktree_root, event=event)
    except Exception:
        latest_ref, history_prefix = checkpoint_refs(identity)
        return CheckpointResult(
            False,
            "checkpoint-failed",
            identity,
            latest_ref=latest_ref,
            history_prefix=history_prefix,
        )


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()
