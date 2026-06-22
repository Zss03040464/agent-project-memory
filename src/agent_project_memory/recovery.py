"""Privacy-safe recovery artifacts and best-effort transcript indexing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from .io import atomic_write_text, write_json_state


RECOVERY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TranscriptTailIndex:
    exists: bool
    size_bytes: int = 0
    last_record_type: Optional[str] = None
    parse_errors: int = 0


def index_transcript_tail(
    path: Optional[Path], *, max_bytes: int = 64 * 1024
) -> TranscriptTailIndex:
    """Index only metadata from a transcript tail; never retain raw content."""

    if path is None:
        return TranscriptTailIndex(False)
    transcript = Path(path)
    try:
        size = transcript.stat().st_size
        with transcript.open("rb") as handle:
            handle.seek(max(0, size - max_bytes))
            raw = handle.read(max_bytes)
    except OSError:
        return TranscriptTailIndex(False)
    errors = 0
    record_type: Optional[str] = None
    for line in reversed(raw.splitlines()):
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            errors += 1
            continue
        if not isinstance(value, dict):
            continue
        candidate = value.get("type") or value.get("event")
        if candidate is None and isinstance(value.get("payload"), dict):
            candidate = value["payload"].get("type") or value["payload"].get(
                "kind"
            )
        if isinstance(candidate, str):
            record_type = candidate[:80]
            break
    return TranscriptTailIndex(True, size, record_type, errors)


def write_recovery_artifacts(
    state_dir: Path,
    *,
    turn: Mapping[str, Any],
    new_session_id: str,
) -> Tuple[Path, Path, str]:
    """Write recovery JSON/Markdown and return short injected context."""

    transcript = index_transcript_tail(
        Path(turn["transcript_path"])
        if isinstance(turn.get("transcript_path"), str)
        else None
    )
    recovery_json = Path(state_dir) / "recovery.json"
    recovery_markdown = Path(state_dir) / "recovery.md"
    payload = {
        "status": "interrupted",
        "previous_session_id": turn.get("session_id"),
        "previous_turn_id": turn.get("turn_id"),
        "new_session_id": new_session_id,
        "project_root": turn.get("project_root"),
        "repo_id": turn.get("repo_id"),
        "worktree_id": turn.get("worktree_id"),
        "checkpoint_ref": turn.get("checkpoint_ref"),
        "checkpoint_commit": turn.get("checkpoint_commit"),
        "last_completed_tool": turn.get("last_completed_tool"),
        "changed_paths": list(turn.get("changed_paths") or ()),
        "prompt_digest": turn.get("prompt_digest"),
        "prompt_excerpt_redacted": turn.get("prompt_excerpt_redacted"),
        "requires_external_revalidation": True,
        "transcript": {
            "exists": transcript.exists,
            "size_bytes": transcript.size_bytes,
            "last_record_type": transcript.last_record_type,
            "parse_errors": transcript.parse_errors,
        },
        "recovery_order": [
            "project_rules_and_management_files",
            "continuity_state",
            "current_git_and_worktree_checkpoint",
            "transcript_tail_if_needed",
            "external_state_revalidation",
            "update_task_and_handoff",
            "continue_from_verified_evidence",
        ],
    }
    write_json_state(
        recovery_json, payload, schema_version=RECOVERY_SCHEMA_VERSION
    )
    lines = [
        "# Interrupted Turn Recovery",
        "",
        "上一轮没有形成正常 Stop 证据。只能恢复到最后一份持久、可验证的证据。",
        "",
        "## 恢复顺序",
        "",
        "1. 先读取项目规则与管理文件。",
        "2. 读取本目录 `turn.json` 和 `recovery.json`。",
        "3. 查看当前 Git/worktree 状态和专属 checkpoint；不要自动覆盖工作区。",
        "4. 仅在管理文件和 Git 无法解释状态时按需检查 transcript 尾部。",
        "5. 重新验证远程服务、进程、端口、GUI 和网页等外部状态。",
        "6. 先更新任务与交接，再从最后有证据的步骤继续。",
        "",
        "## 当前证据",
        "",
        "- checkpoint ref: `{}`".format(
            turn.get("checkpoint_ref") or "none"
        ),
        "- checkpoint commit: `{}`".format(
            turn.get("checkpoint_commit") or "none"
        ),
        "- last completed tool: `{}`".format(
            turn.get("last_completed_tool") or "unknown"
        ),
        "- changed paths: {}".format(
            ", ".join(turn.get("changed_paths") or ()) or "none"
        ),
        "",
        "未写盘的思考、未返回工具调用和 GUI 临时状态无法恢复，必须重新执行或验证。",
        "",
    ]
    atomic_write_text(recovery_markdown, "\n".join(lines))
    context = (
        "检测到上一 session 的未关闭 turn，已先冻结当前磁盘状态并生成恢复文件。"
        "先读取项目规则与管理文件，再读取 "
        + str(recovery_markdown)
        + "；比较当前 worktree 与专属 checkpoint，不要自动覆盖工作区，"
        "并重新验证外部实时状态后继续。"
    )
    return recovery_json, recovery_markdown, context
