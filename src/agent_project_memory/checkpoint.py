"""Worktree-isolated hidden Git checkpoints."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .identity import GitIdentity, discover_git_identity
from .io import ensure_private_directory, process_lock, read_json_state, write_json_state
from .privacy import classify_sensitive_path, scan_sensitive_text


LEGACY_LATEST_REF = "refs/codex/checkpoints/latest"
LEGACY_HISTORY_PREFIX = "refs/codex/checkpoints/history/"
DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 100 * 1024 * 1024
DEFAULT_SCAN_BYTES = 1024 * 1024
DEFAULT_DEBOUNCE_SECONDS = 20
DEFAULT_RETENTION = 20
STATE_SCHEMA_VERSION = 1

_DENIED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".playwright-cli",
    "local storage",
    "session storage",
    "output",
    "dist",
    "build",
    "coverage",
}


@dataclass(frozen=True)
class CheckpointResult:
    created: bool
    reason: str
    identity: Optional[GitIdentity]
    commit: Optional[str] = None
    tree: Optional[str] = None
    latest_ref: Optional[str] = None
    history_ref: Optional[str] = None
    history_prefix: Optional[str] = None
    state_dir: Optional[Path] = None
    skipped_categories: Tuple[str, ...] = ()


def create_git_checkpoint(
    cwd: Path,
    *,
    event: str,
    debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS,
    retention: int = DEFAULT_RETENTION,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    scan_bytes: int = DEFAULT_SCAN_BYTES,
) -> CheckpointResult:
    """Capture allowed disk changes without touching normal Git state."""

    identity = discover_git_identity(Path(cwd))
    if identity is None:
        return CheckpointResult(False, "not-git", None)
    latest_ref, history_prefix = checkpoint_refs(identity)
    state_dir = ensure_private_directory(
        identity.git_dir / "codex-checkpoints-v2"
    )
    lock_path = state_dir / "checkpoint.lock"
    with process_lock(lock_path):
        state_result = read_json_state(
            state_dir / "state.json",
            schema_version=STATE_SCHEMA_VERSION,
            default={},
        )
        state = state_result.data
        if _should_debounce(event, state, debounce_seconds):
            return CheckpointResult(
                False,
                "debounced",
                identity,
                latest_ref=latest_ref,
                history_prefix=history_prefix,
                state_dir=state_dir,
            )
        candidates, skipped = _allowed_candidates(
            identity,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            scan_bytes=scan_bytes,
        )
        if not candidates:
            return CheckpointResult(
                False,
                "no-allowed-changes",
                identity,
                latest_ref=latest_ref,
                history_prefix=history_prefix,
                state_dir=state_dir,
                skipped_categories=skipped,
            )
        tree = _write_checkpoint_tree(identity, candidates, state_dir)
        latest_commit = _read_ref(identity.worktree_root, latest_ref)
        if latest_commit:
            latest_tree = _git_text(
                identity.worktree_root,
                "rev-parse",
                "{}^{{tree}}".format(latest_ref),
                check=False,
            )
            if latest_tree == tree:
                return CheckpointResult(
                    False,
                    "duplicate-tree",
                    identity,
                    commit=latest_commit,
                    tree=tree,
                    latest_ref=latest_ref,
                    history_prefix=history_prefix,
                    state_dir=state_dir,
                    skipped_categories=skipped,
                )
        commit = _commit_tree(identity, tree, event)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
        history_ref = "{}{}-{}".format(history_prefix, timestamp, tree[:12])
        _git(identity.worktree_root, "update-ref", history_ref, commit)
        _git(identity.worktree_root, "update-ref", latest_ref, commit)
        _prune_history(identity.worktree_root, history_prefix, retention)
        write_json_state(
            state_dir / "state.json",
            {
                "last_checkpoint_at": dt.datetime.now(
                    dt.timezone.utc
                ).timestamp(),
                "last_commit": commit,
                "last_tree": tree,
                "latest_ref": latest_ref,
                "worktree_id": identity.worktree_id,
            },
            schema_version=STATE_SCHEMA_VERSION,
        )
        return CheckpointResult(
            True,
            "created",
            identity,
            commit=commit,
            tree=tree,
            latest_ref=latest_ref,
            history_ref=history_ref,
            history_prefix=history_prefix,
            state_dir=state_dir,
            skipped_categories=skipped,
        )


def checkpoint_refs(identity: GitIdentity) -> Tuple[str, str]:
    base = "refs/codex/checkpoints/worktrees/{}".format(identity.worktree_id)
    return base + "/latest", base + "/history/"


def legacy_checkpoint_refs(cwd: Path) -> Tuple[str, ...]:
    identity = discover_git_identity(Path(cwd))
    if identity is None:
        return ()
    refs: List[str] = []
    if _read_ref(identity.worktree_root, LEGACY_LATEST_REF):
        refs.append(LEGACY_LATEST_REF)
    history = _git_text(
        identity.worktree_root,
        "for-each-ref",
        "--format=%(refname)",
        LEGACY_HISTORY_PREFIX,
        check=False,
    )
    refs.extend(line for line in history.splitlines() if line)
    return tuple(refs)


def changed_worktree_paths(cwd: Path) -> Tuple[str, ...]:
    """Return non-sensitive changed relative paths for continuity summaries."""

    identity = discover_git_identity(Path(cwd))
    if identity is None:
        return ()
    safe: List[str] = []
    for raw_path in _changed_paths(identity):
        relative = os.fsdecode(raw_path)
        path = identity.worktree_root / relative
        if _path_skip_category(identity.worktree_root, relative, path) is None:
            safe.append(relative)
    return tuple(safe)


def _should_debounce(event: str, state: Dict[str, object], seconds: int) -> bool:
    if event != "PostToolUse" or seconds <= 0:
        return False
    value = state.get("last_checkpoint_at")
    try:
        elapsed = dt.datetime.now(dt.timezone.utc).timestamp() - float(value)
    except (TypeError, ValueError):
        return False
    return elapsed < seconds


def _allowed_candidates(
    identity: GitIdentity,
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    scan_bytes: int,
) -> Tuple[List[bytes], Tuple[str, ...]]:
    candidates = _changed_paths(identity)
    lfs = _lfs_paths(identity.worktree_root, candidates)
    allowed: List[bytes] = []
    skipped: List[str] = []
    total = 0
    for raw_path in candidates:
        relative = os.fsdecode(raw_path)
        path = identity.worktree_root / relative
        category = _path_skip_category(identity.worktree_root, relative, path)
        if category:
            skipped.append(category)
            continue
        if path.is_symlink():
            try:
                total += len(os.readlink(path).encode("utf-8"))
            except OSError:
                pass
        elif path.is_file() and raw_path not in lfs:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            if size > max_file_bytes:
                skipped.append("file-too-large")
                continue
            if _file_has_sensitive_text(path, scan_bytes):
                skipped.append("sensitive-content")
                continue
            total += size
        allowed.append(raw_path)
    if total > max_total_bytes:
        return [], tuple(sorted(set(skipped + ["total-size-limit"])))
    return allowed, tuple(sorted(set(skipped)))


def _changed_paths(identity: GitIdentity) -> List[bytes]:
    paths: Set[bytes] = set()
    if identity.head is None:
        tracked = _git(identity.worktree_root, "ls-files", "-z").stdout
    else:
        tracked = _git(
            identity.worktree_root,
            "diff",
            "--name-only",
            "-z",
            "HEAD",
            "--",
        ).stdout
    untracked = _git(
        identity.worktree_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    ).stdout
    paths.update(item for item in tracked.split(b"\0") if item)
    paths.update(item for item in untracked.split(b"\0") if item)
    return sorted(paths)


def _path_skip_category(repo: Path, relative: str, path: Path) -> Optional[str]:
    folded_parts = {part.casefold() for part in Path(relative).parts}
    if folded_parts.intersection(_DENIED_DIRS):
        return "denied-directory"
    if classify_sensitive_path(Path(relative)).is_sensitive:
        return "sensitive-path"
    if _inside_nested_repository(repo, path):
        return "nested-repository"
    return None


def _inside_nested_repository(repo: Path, path: Path) -> bool:
    current = path if path.is_dir() else path.parent
    while current != repo and repo in current.parents:
        if (current / ".git").exists():
            return True
        current = current.parent
    return False


def _file_has_sensitive_text(path: Path, scan_bytes: int) -> bool:
    try:
        with path.open("rb") as handle:
            data = handle.read(max(0, scan_bytes) + 1)
    except OSError:
        return False
    if b"\0" in data[:8192]:
        return False
    text = data.decode("utf-8", "ignore")
    return scan_sensitive_text(text).is_sensitive


def _lfs_paths(repo: Path, candidates: Sequence[bytes]) -> Set[bytes]:
    if not candidates:
        return set()
    result = _git(
        repo,
        "check-attr",
        "-z",
        "--stdin",
        "filter",
        input_bytes=b"\0".join(candidates) + b"\0",
        check=False,
    )
    if result.returncode:
        return set()
    fields = result.stdout.split(b"\0")
    found: Set[bytes] = set()
    for index in range(0, len(fields) - 2, 3):
        path, attribute, value = fields[index : index + 3]
        if attribute == b"filter" and value == b"lfs":
            found.add(path)
    return found


def _write_checkpoint_tree(
    identity: GitIdentity, candidates: Sequence[bytes], state_dir: Path
) -> str:
    descriptor, name = tempfile.mkstemp(prefix="index-", dir=str(state_dir))
    os.close(descriptor)
    os.unlink(name)
    index_path = Path(name)
    env = _checkpoint_environment(index_path)
    try:
        if identity.head is None:
            _git(identity.worktree_root, "read-tree", "--empty", env=env)
        else:
            _git(identity.worktree_root, "read-tree", "HEAD", env=env)
        _git(
            identity.worktree_root,
            "add",
            "-A",
            "--pathspec-from-file=-",
            "--pathspec-file-nul",
            env=env,
            input_bytes=b"\0".join(candidates) + b"\0",
        )
        return _git_text(identity.worktree_root, "write-tree", env=env)
    finally:
        try:
            index_path.unlink()
        except FileNotFoundError:
            pass


def _commit_tree(identity: GitIdentity, tree: str, event: str) -> str:
    args = ["commit-tree", tree]
    if identity.head is not None:
        args.extend(["-p", "HEAD"])
    result = _git(
        identity.worktree_root,
        *args,
        env=_checkpoint_environment(None),
        input_bytes=(
            "Agent Project Memory checkpoint\n\nTrigger: {}\n".format(event)
        ).encode("utf-8"),
    )
    return result.stdout.decode("ascii").strip()


def _checkpoint_environment(index_path: Optional[Path]) -> Dict[str, str]:
    env = os.environ.copy()
    if index_path is not None:
        env["GIT_INDEX_FILE"] = str(index_path)
    env.update(
        {
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_AUTHOR_NAME": "Agent Project Memory",
            "GIT_AUTHOR_EMAIL": "agent-project-memory@invalid",
            "GIT_COMMITTER_NAME": "Agent Project Memory",
            "GIT_COMMITTER_EMAIL": "agent-project-memory@invalid",
        }
    )
    return env


def _prune_history(repo: Path, prefix: str, retention: int) -> None:
    keep = max(0, retention)
    output = _git_text(
        repo,
        "for-each-ref",
        "--format=%(refname)",
        prefix,
        check=False,
    )
    refs = sorted(line for line in output.splitlines() if line)
    for ref in refs[: max(0, len(refs) - keep)]:
        _git(repo, "update-ref", "-d", ref)


def _read_ref(repo: Path, ref: str) -> Optional[str]:
    value = _git_text(repo, "rev-parse", "--verify", ref, check=False)
    return value or None


def _git(
    cwd: Path,
    *args: str,
    env: Optional[Dict[str, str]] = None,
    input_bytes: Optional[bytes] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode:
        raise RuntimeError("git checkpoint command failed")
    return result


def _git_text(
    cwd: Path,
    *args: str,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
) -> str:
    return _git(cwd, *args, env=env, check=check).stdout.decode(
        "utf-8", "surrogateescape"
    ).strip()
