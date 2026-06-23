"""Evidence-based completion gate."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

from .privacy import classify_sensitive_path, scan_sensitive_text


_HIGH_CONFIDENCE_CONTENT_CATEGORIES = frozenset(
    {
        "private_key",
        "openai_token",
        "github_token",
        "aws_access_key",
        "authorization_header",
        "cookie_header",
    }
)
_CONFIG_DATA_SUFFIXES = frozenset(
    {".cfg", ".conf", ".config", ".ini", ".json", ".toml", ".yaml", ".yml"}
)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    hard_failures: Tuple[str, ...]
    warnings: Tuple[str, ...]


def capture_git_state(project_root: Path) -> Optional[Tuple[str, str, str, str]]:
    root = Path(project_root)
    try:
        status = _git(root, "status", "--porcelain=v2", "-z")
        try:
            head = _git(root, "rev-parse", "--verify", "HEAD")
        except RuntimeError:
            if _git(root, "rev-parse", "--is-inside-work-tree").strip() != "true":
                raise
            head = ""
        return (
            status,
            head,
            _git(root, "branch", "--show-current"),
            _git(root, "write-tree"),
        )
    except RuntimeError:
        return None


def run_completion_gate(
    project_root: Path,
    *,
    required_requirements: Tuple[str, ...],
    evidence: Mapping[str, bool],
    expected_git_state: Optional[Tuple[str, str, str, str]],
) -> GateResult:
    root = Path(project_root)
    failures = []
    warnings = []
    for requirement in required_requirements:
        if not evidence.get(requirement, False):
            failures.append("missing-evidence:" + requirement)
    if _contains_sensitive_content(root):
        failures.append("sensitive-content")
    if expected_git_state != capture_git_state(root):
        failures.append("git-state-pollution")
    for name in ("任务.md", "交接.md"):
        if not (root / name).is_file():
            warnings.append("missing-management-file:" + name)
    duplicates = [
        path.name
        for path in root.iterdir()
        if path.is_file()
        and any(token in path.stem.casefold() for token in (" copy", "副本", "final2"))
    ]
    if duplicates:
        warnings.append("duplicate-looking-output")
    return GateResult(not failures, tuple(failures), tuple(warnings))


def _contains_sensitive_content(root: Path) -> bool:
    for path in root.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        relative = path.relative_to(root)
        if classify_sensitive_path(relative).is_sensitive:
            return True
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        scan = scan_sensitive_text(data.decode("utf-8", "ignore"))
        if _content_categories_are_sensitive(relative, scan.categories):
            return True
    return False


def _content_categories_are_sensitive(
    relative: Path, categories: Tuple[str, ...]
) -> bool:
    detected = set(categories)
    if detected.intersection(_HIGH_CONFIDENCE_CONTENT_CATEGORIES):
        return True
    return (
        "secret_assignment" in detected
        and relative.suffix.casefold() in _CONFIG_DATA_SUFFIXES
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError("git state unavailable")
    return result.stdout.decode("utf-8", "surrogateescape")
