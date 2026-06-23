"""Typed configuration loading with fail-open, privacy-safe diagnostics."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union


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


@dataclass(frozen=True)
class RootClassification:
    is_dangerous: bool
    category: str
    requires_project_marker: bool = False


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
        values = parse_toml_subset(raw)
        if set(values) - _FIELDS:
            raise ValueError("unknown field")
        config, ignored_count = _build_config(values, defaults)
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeError):
        return ConfigLoadResult(
            defaults, ("invalid configuration; using safe defaults",)
        )
    diagnostics: Tuple[str, ...] = ()
    if ignored_count:
        diagnostics = ("unsafe or denied trusted roots ignored",)
    return ConfigLoadResult(config, diagnostics)


def parse_toml_subset(raw: bytes) -> Dict[str, Any]:
    """Parse the strict flat TOML subset used by continuity configuration."""

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
        parsed[key] = _TomlValueParser(literal.strip()).parse()
    return parsed


def _logical_statements(text: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    escaped = False
    bracket_depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        if quote is not None:
            current.append(character)
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            elif character in "\r\n":
                raise ValueError("multiline strings are not supported")
            index += 1
            continue
        if character in {'"', "'"}:
            quote = character
            current.append(character)
        elif character == "#":
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        elif character == "[":
            bracket_depth += 1
            current.append(character)
        elif character == "]":
            bracket_depth -= 1
            if bracket_depth < 0:
                raise ValueError("unbalanced array")
            current.append(character)
        elif character in "\r\n":
            if bracket_depth == 0:
                statement = "".join(current).strip()
                if statement:
                    statements.append(statement)
                current = []
            else:
                current.append(" ")
        else:
            current.append(character)
        index += 1
    if quote is not None or bracket_depth != 0:
        raise ValueError("unterminated TOML value")
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


class _TomlValueParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.index = 0

    def parse(self) -> Any:
        value = self._parse_value()
        self._skip_space()
        if self.index != len(self.text):
            raise ValueError("trailing TOML content")
        return value

    def _parse_value(self) -> Any:
        self._skip_space()
        if self.index >= len(self.text):
            raise ValueError("missing TOML value")
        character = self.text[self.index]
        if character == '"':
            return self._parse_basic_string()
        if character == "'":
            return self._parse_literal_string()
        if character == "[":
            return self._parse_array()
        if self.text.startswith("true", self.index):
            self.index += 4
            return True
        if self.text.startswith("false", self.index):
            self.index += 5
            return False
        return self._parse_integer()

    def _parse_basic_string(self) -> str:
        self.index += 1
        result: List[str] = []
        escapes = {
            '"': '"',
            "\\": "\\",
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "f": "\f",
            "r": "\r",
        }
        while self.index < len(self.text):
            character = self.text[self.index]
            self.index += 1
            if character == '"':
                return "".join(result)
            if character != "\\":
                if ord(character) < 0x20:
                    raise ValueError("control character in basic string")
                result.append(character)
                continue
            if self.index >= len(self.text):
                raise ValueError("unterminated escape")
            escaped = self.text[self.index]
            self.index += 1
            if escaped in escapes:
                result.append(escapes[escaped])
            elif escaped in {"u", "U"}:
                width = 4 if escaped == "u" else 8
                digits = self.text[self.index : self.index + width]
                if len(digits) != width or not re.fullmatch(
                    r"[0-9A-Fa-f]+", digits
                ):
                    raise ValueError("invalid unicode escape")
                codepoint = int(digits, 16)
                if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                    raise ValueError("invalid unicode codepoint")
                result.append(chr(codepoint))
                self.index += width
            else:
                raise ValueError("unsupported TOML escape")
        raise ValueError("unterminated basic string")

    def _parse_literal_string(self) -> str:
        self.index += 1
        end = self.text.find("'", self.index)
        if end < 0:
            raise ValueError("unterminated literal string")
        value = self.text[self.index : end]
        if any(character in "\r\n" for character in value):
            raise ValueError("multiline literal strings are not supported")
        self.index = end + 1
        return value

    def _parse_array(self) -> List[Any]:
        self.index += 1
        values = []
        self._skip_space()
        if self._consume("]"):
            return values
        while True:
            values.append(self._parse_value())
            self._skip_space()
            if self._consume("]"):
                return values
            if not self._consume(","):
                raise ValueError("array comma required")
            self._skip_space()
            if self._consume("]"):
                return values

    def _parse_integer(self) -> int:
        match = re.match(
            r"[+-]?(?:0|[1-9](?:_?[0-9])*)", self.text[self.index :]
        )
        if match is None:
            raise ValueError("unsupported TOML value")
        token = match.group(0)
        self.index += len(token)
        return int(token.replace("_", ""))

    def _consume(self, expected: str) -> bool:
        if self.text.startswith(expected, self.index):
            self.index += len(expected)
            return True
        return False

    def _skip_space(self) -> None:
        while self.index < len(self.text) and self.text[self.index] in " \t":
            self.index += 1


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

    project_markers = tuple(
        values.get("project_markers", defaults.project_markers)
    )
    _validate_project_markers(project_markers)
    denied = _deduplicate_paths(
        tuple(defaults.denied_roots)
        + tuple(_normalize_path(item) for item in values.get("denied_roots", ()))
    )
    trusted: List[Path] = []
    ignored_count = 0
    for item in values.get("trusted_roots", ()):
        candidate = _normalize_path(item)
        classification = classify_root(
            candidate,
            home=Path.home().resolve(),
            has_project_marker=_has_project_marker(candidate, project_markers),
        )
        if classification.is_dangerous or any(
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
            project_markers=project_markers,
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
    candidate = Path(os.path.expandvars(value)).expanduser()
    if not candidate.is_absolute():
        raise ValueError("configured roots must be absolute")
    try:
        if candidate.is_symlink():
            return candidate.resolve(strict=True)
        return candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError("configured root cannot be resolved") from exc


def _deduplicate_paths(paths: Iterable[Path]) -> Tuple[Path, ...]:
    result: List[Path] = []
    for path in paths:
        normalized = _normalize_path(str(path))
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _is_same_or_descendant(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def classify_root(
    path: Union[str, PurePath],
    *,
    home: Optional[Union[str, PurePath]] = None,
    has_project_marker: bool = False,
) -> RootClassification:
    candidate = _as_pure_path(path)
    profile = _as_pure_path(home if home is not None else Path.home())
    if type(candidate) is not type(profile):
        raise ValueError("path and home must use the same platform flavor")
    if not candidate.is_absolute():
        return RootClassification(True, "relative")

    if isinstance(candidate, PureWindowsPath):
        drive_root = PureWindowsPath(candidate.anchor)
        users_root = drive_root / "Users"
        if candidate in {drive_root, users_root, profile}:
            return RootClassification(True, "broad_container")
    else:
        if candidate in {
            PurePosixPath("/"),
            PurePosixPath("/home"),
            PurePosixPath("/Users"),
            profile,
        }:
            return RootClassification(True, "broad_container")

    if _is_relative_to(candidate, profile / ".codex"):
        return RootClassification(True, "codex_state")

    sync_kind = _sync_root_kind(candidate, profile)
    if sync_kind in {"container", "provider"}:
        return RootClassification(True, "sync_provider")
    if sync_kind == "descendant":
        return RootClassification(
            not has_project_marker,
            "sync_project" if has_project_marker else "sync_unmarked",
            requires_project_marker=True,
        )
    return RootClassification(False, "project")


def _sync_root_kind(path: PurePath, home: PurePath) -> Optional[str]:
    home_parts = _relative_parts(path, home)
    if home_parts is not None:
        folded = tuple(part.casefold() for part in home_parts)
        if folded:
            first = folded[0]
            if _is_sync_provider_name(first):
                return "provider" if len(folded) == 1 else "descendant"
        for prefix in (
            ("library", "cloudstorage"),
            ("library", "mobile documents"),
        ):
            if folded[:2] == prefix:
                if len(folded) == 2:
                    return "container"
                if len(folded) == 3:
                    return "provider"
                return "descendant"

    if isinstance(path, PurePosixPath):
        volume_parts = _relative_parts(path, PurePosixPath("/Volumes"))
        if volume_parts is not None:
            if not volume_parts:
                return "container"
            return "provider" if len(volume_parts) == 1 else "descendant"
    return None


def _is_sync_provider_name(name: str) -> bool:
    return (
        name.startswith("dropbox")
        or name.startswith("onedrive")
        or name.startswith("google drive")
        or name.startswith("googledrive")
    )


def _as_pure_path(value: Union[str, PurePath]) -> PurePath:
    if isinstance(value, PureWindowsPath):
        return value
    if isinstance(value, PurePosixPath):
        return value
    text = str(value)
    if re.match(r"^[A-Za-z]:[\\/]", text) or "\\" in text:
        return PureWindowsPath(text)
    return PurePosixPath(text)


def _relative_parts(path: PurePath, root: PurePath) -> Optional[Tuple[str, ...]]:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return None


def _is_relative_to(path: PurePath, root: PurePath) -> bool:
    return _relative_parts(path, root) is not None


def _validate_project_markers(markers: Tuple[str, ...]) -> None:
    for marker in markers:
        marker_path = PurePosixPath(marker)
        if marker_path.is_absolute() or ".." in marker_path.parts:
            raise ValueError("project markers must be relative names")


def _has_project_marker(path: Path, markers: Tuple[str, ...]) -> bool:
    try:
        return any((path / marker).exists() for marker in markers)
    except OSError:
        return False
