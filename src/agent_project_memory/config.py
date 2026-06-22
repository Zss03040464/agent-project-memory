"""Typed configuration loading with fail-open, privacy-safe diagnostics."""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


_FIELDS = {
    "trusted_roots",
    "denied_roots",
    "project_markers",
    "max_file_bytes",
    "max_total_bytes",
    "checkpoint_debounce_seconds",
    "checkpoint_retention",
    "prompt_excerpt_bytes",
    "feedback_promotion_threshold",
    "log_max_bytes",
    "hard_fail_checks",
    "warning_checks",
}
_LIST_FIELDS = {
    "trusted_roots",
    "denied_roots",
    "project_markers",
    "hard_fail_checks",
    "warning_checks",
}
_INTEGER_FIELDS = _FIELDS - _LIST_FIELDS
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Config:
    trusted_roots: Tuple[Path, ...]
    denied_roots: Tuple[Path, ...]
    project_markers: Tuple[str, ...]
    max_file_bytes: int
    max_total_bytes: int
    checkpoint_debounce_seconds: int
    checkpoint_retention: int
    prompt_excerpt_bytes: int
    feedback_promotion_threshold: int
    log_max_bytes: int
    hard_fail_checks: Tuple[str, ...]
    warning_checks: Tuple[str, ...]

    @classmethod
    def defaults(cls) -> "Config":
        home = Path.home().resolve()
        return cls(
            trusted_roots=(),
            denied_roots=_deduplicate_paths(
                (
                    home / ".codex",
                    home / "Downloads",
                )
            ),
            project_markers=(".git", "pyproject.toml", "package.json", "Cargo.toml"),
            max_file_bytes=1024 * 1024,
            max_total_bytes=8 * 1024 * 1024,
            checkpoint_debounce_seconds=15,
            checkpoint_retention=20,
            prompt_excerpt_bytes=2048,
            feedback_promotion_threshold=2,
            log_max_bytes=1024 * 1024,
            hard_fail_checks=("privacy", "state"),
            warning_checks=("docs",),
        )


@dataclass(frozen=True)
class ConfigLoadResult:
    config: Config
    diagnostics: Tuple[str, ...] = ()


def load_config(path: Path) -> ConfigLoadResult:
    """Load a flat TOML configuration, falling back safely on any problem."""

    defaults = Config.defaults()
    config_path = Path(path)
    if not config_path.exists():
        return ConfigLoadResult(defaults)
    try:
        raw = config_path.read_bytes()
    except OSError:
        return ConfigLoadResult(
            defaults, ("configuration unreadable; using safe defaults",)
        )
    try:
        values = _parse_flat_toml(raw)
        config, ignored_count = _build_config(values, defaults)
    except (ValueError, TypeError, UnicodeError, SyntaxError):
        return ConfigLoadResult(
            defaults, ("invalid configuration; using safe defaults",)
        )
    diagnostics: Tuple[str, ...] = ()
    if ignored_count:
        diagnostics = ("unsafe or denied trusted roots ignored",)
    return ConfigLoadResult(config, diagnostics)


def _parse_flat_toml(raw: bytes) -> Dict[str, Any]:
    """Parse the deliberately small, flat TOML schema on Python 3.9+.

    The supported values are integers, quoted strings, and arrays of quoted
    strings. This covers the complete public schema without a runtime package.
    """

    text = raw.decode("utf-8")
    statements = _logical_statements(text)
    parsed: Dict[str, Any] = {}
    for statement in statements:
        if statement.startswith("["):
            raise ValueError("tables are not supported")
        key, separator, literal = statement.partition("=")
        key = key.strip()
        if not separator or not _KEY_RE.fullmatch(key) or key in parsed:
            raise ValueError("invalid assignment")
        if key not in _FIELDS:
            raise ValueError("unknown field")
        parsed[key] = ast.literal_eval(literal.strip())
    return parsed


def _logical_statements(text: str) -> List[str]:
    statements: List[str] = []
    pending: List[str] = []
    bracket_depth = 0
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        pending.append(line)
        bracket_depth += _bracket_delta(line)
        if bracket_depth < 0:
            raise ValueError("unbalanced array")
        if bracket_depth == 0:
            statements.append(" ".join(pending))
            pending = []
    if pending or bracket_depth:
        raise ValueError("unterminated assignment")
    return statements


def _strip_comment(line: str) -> str:
    quote = ""
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote:
            escaped = True
            continue
        if character in {'"', "'"}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            continue
        if character == "#" and not quote:
            return line[:index]
    if quote:
        raise ValueError("unterminated string")
    return line


def _bracket_delta(line: str) -> int:
    quote = ""
    escaped = False
    delta = 0
    for character in line:
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote:
            escaped = True
            continue
        if character in {'"', "'"}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            continue
        if not quote:
            delta += character == "["
            delta -= character == "]"
    return delta


def _build_config(values: Mapping[str, Any], defaults: Config) -> Tuple[Config, int]:
    for field in _LIST_FIELDS:
        if field in values and not _is_string_list(values[field]):
            raise TypeError("list field has wrong type")
    for field in _INTEGER_FIELDS:
        if field in values and (
            type(values[field]) is not int or values[field] <= 0
        ):
            raise TypeError("integer field has wrong type")

    max_file_bytes = values.get("max_file_bytes", defaults.max_file_bytes)
    max_total_bytes = values.get("max_total_bytes", defaults.max_total_bytes)
    feedback_threshold = values.get(
        "feedback_promotion_threshold",
        defaults.feedback_promotion_threshold,
    )
    if max_total_bytes < max_file_bytes or feedback_threshold < 2:
        raise ValueError("unsafe numeric configuration")

    denied = _deduplicate_paths(
        tuple(defaults.denied_roots)
        + tuple(_normalize_path(item) for item in values.get("denied_roots", ()))
    )
    trusted: List[Path] = []
    ignored_count = 0
    for item in values.get("trusted_roots", ()):
        candidate = _normalize_path(item)
        if _is_dangerous_root(candidate) or any(
            _is_same_or_descendant(candidate, denied_root)
            for denied_root in denied
        ):
            ignored_count += 1
            continue
        if candidate not in trusted:
            trusted.append(candidate)

    return (
        Config(
            trusted_roots=tuple(trusted),
            denied_roots=denied,
            project_markers=tuple(
                values.get("project_markers", defaults.project_markers)
            ),
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            checkpoint_debounce_seconds=values.get(
                "checkpoint_debounce_seconds",
                defaults.checkpoint_debounce_seconds,
            ),
            checkpoint_retention=values.get(
                "checkpoint_retention", defaults.checkpoint_retention
            ),
            prompt_excerpt_bytes=values.get(
                "prompt_excerpt_bytes", defaults.prompt_excerpt_bytes
            ),
            feedback_promotion_threshold=feedback_threshold,
            log_max_bytes=values.get("log_max_bytes", defaults.log_max_bytes),
            hard_fail_checks=tuple(
                values.get("hard_fail_checks", defaults.hard_fail_checks)
            ),
            warning_checks=tuple(
                values.get("warning_checks", defaults.warning_checks)
            ),
        ),
        ignored_count,
    )


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def _normalize_path(value: str) -> Path:
    if "\x00" in value:
        raise ValueError("invalid path")
    return Path(os.path.expandvars(value)).expanduser().resolve()


def _deduplicate_paths(paths: Iterable[Path]) -> Tuple[Path, ...]:
    result: List[Path] = []
    for path in paths:
        normalized = Path(path).expanduser().resolve()
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _is_same_or_descendant(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_dangerous_root(path: Path) -> bool:
    home = Path.home().resolve()
    exact_roots = {
        Path(os.sep).resolve(),
        home,
        Path("/Users").resolve(),
    }
    if path in exact_roots:
        return True
    return _is_same_or_descendant(path, home / ".codex")
