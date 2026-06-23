"""Safe automatic project discovery, Git initialization, and external snapshots."""

from __future__ import annotations

import hashlib
import os
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .checkpoint import create_git_checkpoint
from .config import Config, classify_root
from .identity import discover_git_identity
from .io import atomic_write_text, ensure_private_directory
from .privacy import classify_sensitive_path, scan_sensitive_text


_DEFAULT_GITIGNORE = """# Agent Project Memory safety defaults
.env
.env.*
*.pem
*.key
*.p12
*.pfx
auth.json
credentials*
secrets*
cookie*
node_modules/
.venv/
venv/
__pycache__/
.playwright-cli/
dist/
build/
coverage/
"""

_DENIED_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".playwright-cli",
    "dist",
    "build",
    "coverage",
}


@dataclass(frozen=True)
class ProjectRootResult:
    root: Path
    kind: str
    marker: Optional[str] = None
    trusted: bool = False
    dangerous: bool = False


@dataclass(frozen=True)
class BootstrapResult:
    mode: str
    project_root: Path
    initialized_git: bool = False
    checkpoint_commit: Optional[str] = None
    external_git_dir: Optional[Path] = None
    project_id: Optional[str] = None
    scanned_files: int = 0
    reason: str = ""


def identify_project_root(cwd: Path, *, config: Config) -> ProjectRootResult:
    location = Path(cwd)
    identity = discover_git_identity(location)
    if identity is not None:
        return ProjectRootResult(
            identity.worktree_root, "git", trusted=True
        )
    try:
        canonical = location.resolve()
    except (OSError, RuntimeError):
        return ProjectRootResult(location.absolute(), "unknown", dangerous=True)
    if _denied_or_broad(canonical, config):
        return ProjectRootResult(canonical, "excluded", dangerous=True)
    marker_root, marker = _find_marker_root(canonical, config.project_markers)
    if marker_root is not None:
        if _denied_or_broad(marker_root, config):
            return ProjectRootResult(
                marker_root, "excluded", marker=marker, dangerous=True
            )
        return ProjectRootResult(
            marker_root,
            "marked",
            marker=marker,
            trusted=_inside_any(marker_root, config.trusted_roots),
        )
    trusted = _inside_any(canonical, config.trusted_roots)
    empty = _is_empty_directory(canonical)
    return ProjectRootResult(
        canonical,
        "empty" if empty else "unmarked",
        trusted=trusted,
    )


def bootstrap_project(
    cwd: Path, *, config: Config, codex_home: Path
) -> BootstrapResult:
    found = identify_project_root(Path(cwd), config=config)
    if found.kind == "excluded" or found.dangerous:
        return BootstrapResult(
            "excluded", found.root, scanned_files=0, reason="dangerous-root"
        )
    if found.kind == "git":
        checkpoint = create_git_checkpoint(
            found.root,
            event="Bootstrap",
            debounce_seconds=config.checkpoint_debounce_seconds,
            retention=config.checkpoint_retention,
            max_file_bytes=config.max_file_bytes,
            max_total_bytes=config.max_total_bytes,
        )
        return BootstrapResult(
            "git",
            found.root,
            checkpoint_commit=checkpoint.commit,
            reason=checkpoint.reason,
        )
    if found.trusted and found.kind in {"marked", "empty"}:
        if _contains_nested_git(found.root):
            return _external_checkpoint(
                found.root, config=config, codex_home=Path(codex_home)
            )
        _prepare_gitignore(found.root)
        _git(found.root, "init", "-q")
        checkpoint = create_git_checkpoint(
            found.root,
            event="Bootstrap",
            debounce_seconds=0,
            retention=config.checkpoint_retention,
            max_file_bytes=config.max_file_bytes,
            max_total_bytes=config.max_total_bytes,
        )
        return BootstrapResult(
            "git",
            found.root,
            initialized_git=True,
            checkpoint_commit=checkpoint.commit,
            reason=checkpoint.reason,
        )
    if found.kind in {"marked", "unmarked"}:
        return _external_checkpoint(
            found.root, config=config, codex_home=Path(codex_home)
        )
    return BootstrapResult(
        "excluded", found.root, scanned_files=0, reason="uncertain-project-root"
    )


def _external_checkpoint(
    project_root: Path, *, config: Config, codex_home: Path
) -> BootstrapResult:
    salt = _installation_salt(codex_home)
    project_id = hashlib.sha256(
        salt + b"\0" + os.fsencode(str(project_root.resolve()))
    ).hexdigest()[:32]
    base = ensure_private_directory(
        codex_home / "continuity" / "non_git" / project_id
    )
    git_dir = ensure_private_directory(base / "git-dir")
    if not (git_dir / "HEAD").exists():
        _external_git(git_dir, project_root, "init", "-q")
    candidates = _external_candidates(
        project_root,
        max_file_bytes=config.max_file_bytes,
        max_total_bytes=config.max_total_bytes,
    )
    commit = _write_external_checkpoint(
        git_dir, project_root, candidates
    )
    return BootstrapResult(
        "external",
        project_root,
        checkpoint_commit=commit,
        external_git_dir=git_dir,
        project_id=project_id,
        scanned_files=len(candidates),
        reason="external-checkpoint",
    )


def _write_external_checkpoint(
    git_dir: Path, project_root: Path, candidates: Sequence[bytes]
) -> str:
    descriptor, name = tempfile.mkstemp(
        prefix="index-", dir=str(git_dir.parent)
    )
    os.close(descriptor)
    os.unlink(name)
    index = Path(name)
    env = os.environ.copy()
    env.update(
        {
            "GIT_DIR": str(git_dir),
            "GIT_WORK_TREE": str(project_root),
            "GIT_INDEX_FILE": str(index),
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_AUTHOR_NAME": "Agent Project Memory",
            "GIT_AUTHOR_EMAIL": "agent-project-memory@invalid",
            "GIT_COMMITTER_NAME": "Agent Project Memory",
            "GIT_COMMITTER_EMAIL": "agent-project-memory@invalid",
        }
    )
    try:
        _run(["git", "read-tree", "--empty"], env=env)
        if candidates:
            _run(
                [
                    "git",
                    "add",
                    "-A",
                    "--pathspec-from-file=-",
                    "--pathspec-file-nul",
                ],
                env=env,
                input_bytes=b"\0".join(candidates) + b"\0",
            )
        tree = _run(["git", "write-tree"], env=env).stdout.decode().strip()
        latest = _external_ref(git_dir, "refs/codex/checkpoints/latest")
        if latest:
            latest_tree = _external_git_text(
                git_dir, project_root, "rev-parse", "{}^{{tree}}".format(latest)
            )
            if latest_tree == tree:
                return latest
        args = ["git", "commit-tree", tree]
        if latest:
            args.extend(["-p", latest])
        commit = _run(
            args,
            env=env,
            input_bytes=b"External non-Git checkpoint\n",
        ).stdout.decode().strip()
        _external_git(
            git_dir,
            project_root,
            "update-ref",
            "refs/codex/checkpoints/latest",
            commit,
        )
        return commit
    finally:
        try:
            index.unlink()
        except FileNotFoundError:
            pass


def _external_candidates(
    project_root: Path, *, max_file_bytes: int, max_total_bytes: int
) -> List[bytes]:
    output = _external_git(
        None,
        project_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        temporary=True,
    ).stdout
    allowed: List[bytes] = []
    total = 0
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = os.fsdecode(raw)
        parts = {part.casefold() for part in Path(relative).parts}
        path = project_root / relative
        if parts.intersection(_DENIED_DIR_NAMES):
            continue
        if classify_sensitive_path(Path(relative)).is_sensitive:
            continue
        if _inside_nested_git(project_root, path):
            continue
        if path.is_symlink():
            allowed.append(raw)
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_file_bytes:
            continue
        if _sensitive_file(path):
            continue
        total += size
        allowed.append(raw)
    if total > max_total_bytes:
        return []
    return allowed


def _external_git(
    git_dir: Optional[Path],
    work_tree: Path,
    *args: str,
    temporary: bool = False,
) -> subprocess.CompletedProcess:
    command = ["git"]
    if git_dir is not None:
        command.extend(
            ["--git-dir={}".format(git_dir), "--work-tree={}".format(work_tree)]
        )
    elif temporary:
        with tempfile.TemporaryDirectory(prefix="apm-external-list-") as temp:
            temporary_git = Path(temp) / "git-dir"
            subprocess.run(
                ["git", "init", "-q", "--bare", str(temporary_git)],
                check=True,
            )
            return _run(
                [
                    "git",
                    "--git-dir={}".format(temporary_git),
                    "--work-tree={}".format(work_tree),
                    *args,
                ]
            )
    command.extend(args)
    return _run(command)


def _external_git_text(
    git_dir: Path, work_tree: Path, *args: str
) -> str:
    return _external_git(git_dir, work_tree, *args).stdout.decode().strip()


def _external_ref(git_dir: Path, ref: str) -> Optional[str]:
    result = _run(
        ["git", "--git-dir={}".format(git_dir), "rev-parse", "--verify", ref],
        check=False,
    )
    return result.stdout.decode().strip() if result.returncode == 0 else None


def _installation_salt(codex_home: Path) -> bytes:
    path = codex_home / "continuity" / "install-salt"
    try:
        value = path.read_text(encoding="ascii").strip()
        if len(value) == 64:
            return bytes.fromhex(value)
    except (OSError, ValueError):
        pass
    value = secrets.token_bytes(32)
    atomic_write_text(path, value.hex() + "\n")
    return value


def _prepare_gitignore(project_root: Path) -> None:
    path = project_root / ".gitignore"
    if not path.exists():
        path.write_text(_DEFAULT_GITIGNORE, encoding="utf-8")


def _find_marker_root(
    cwd: Path, markers: Tuple[str, ...]
) -> Tuple[Optional[Path], Optional[str]]:
    current = cwd
    while True:
        for marker in markers:
            try:
                if (current / marker).exists():
                    return current, marker
            except OSError:
                return None, None
        if current.parent == current:
            return None, None
        current = current.parent


def _denied_or_broad(path: Path, config: Config) -> bool:
    if any(_same_or_descendant(path, denied) for denied in config.denied_roots):
        return True
    if any(_same_or_descendant(trusted, path) for trusted in config.trusted_roots):
        return True
    return classify_root(path).is_dangerous


def _inside_any(path: Path, roots: Tuple[Path, ...]) -> bool:
    return any(_same_or_descendant(path, root) for root in roots)


def _same_or_descendant(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_empty_directory(path: Path) -> bool:
    try:
        return path.is_dir() and next(path.iterdir(), None) is None
    except OSError:
        return False


def _inside_nested_git(root: Path, path: Path) -> bool:
    current = path if path.is_dir() else path.parent
    while current != root and root in current.parents:
        if (current / ".git").exists():
            return True
        current = current.parent
    return False


def _contains_nested_git(root: Path) -> bool:
    try:
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if current_path != root and (
                ".git" in directories or ".git" in files
            ):
                return True
            directories[:] = [
                name
                for name in directories
                if name.casefold() not in _DENIED_DIR_NAMES
            ]
    except OSError:
        return True
    return False


def _sensitive_file(path: Path) -> bool:
    try:
        data = path.read_bytes()[: 1024 * 1024]
    except OSError:
        return False
    if b"\0" in data[:8192]:
        return False
    return scan_sensitive_text(data.decode("utf-8", "ignore")).is_sensitive


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", "-C", str(cwd), *args])


def _run(
    command: Sequence[str],
    *,
    env: Optional[Dict[str, str]] = None,
    input_bytes: Optional[bytes] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        list(command),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode:
        raise RuntimeError("project bootstrap command failed")
    return result
