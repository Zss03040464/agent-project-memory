"""Stable Git repository and worktree identity discovery."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GitIdentity:
    repo_root: Path
    worktree_root: Path
    common_dir: Path
    git_dir: Path
    repo_id: str
    worktree_id: str
    head: Optional[str]
    branch: Optional[str]
    detached: bool
    unborn: bool


def discover_git_identity(cwd: Path) -> Optional[GitIdentity]:
    """Return stable Git/worktree identity, or ``None`` outside Git."""

    location = Path(cwd)
    root_result = _git(location, "rev-parse", "--show-toplevel", check=False)
    if root_result.returncode:
        return None
    worktree_root = Path(
        root_result.stdout.decode("utf-8", "surrogateescape").strip()
    ).resolve()
    common_dir = _resolve_git_path(
        worktree_root,
        _git_text(worktree_root, "rev-parse", "--git-common-dir"),
    )
    git_dir = _resolve_git_path(
        worktree_root,
        _git_text(worktree_root, "rev-parse", "--git-dir"),
    )
    head_result = _git(worktree_root, "rev-parse", "--verify", "HEAD", check=False)
    head = (
        head_result.stdout.decode("ascii", "replace").strip()
        if head_result.returncode == 0
        else None
    )
    branch = _git_text(
        worktree_root, "branch", "--show-current", check=False
    ) or None
    return GitIdentity(
        repo_root=worktree_root,
        worktree_root=worktree_root,
        common_dir=common_dir,
        git_dir=git_dir,
        repo_id=_stable_id("repo", str(common_dir)),
        worktree_id=_stable_id(
            "worktree", str(worktree_root), str(git_dir)
        ),
        head=head,
        branch=branch,
        detached=head is not None and branch is None,
        unborn=head is None,
    )


def _stable_id(namespace: str, *values: str) -> str:
    digest = hashlib.sha256()
    digest.update(namespace.encode("ascii"))
    for value in values:
        digest.update(b"\0")
        digest.update(value.encode("utf-8", "surrogateescape"))
    return digest.hexdigest()[:32]


def _resolve_git_path(worktree_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = worktree_root / path
    return path.resolve()


def _git(
    cwd: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError("git identity command failed")
    return result


def _git_text(cwd: Path, *args: str, check: bool = True) -> str:
    return _git(cwd, *args, check=check).stdout.decode(
        "utf-8", "surrogateescape"
    ).strip()
