"""Privacy classification and bounded, non-secret prompt summaries."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Pattern, Tuple


@dataclass(frozen=True)
class PathClassification:
    is_sensitive: bool
    categories: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SensitiveScan:
    is_sensitive: bool
    categories: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptSummary:
    excerpt: str
    digest: str
    redacted: bool
    truncated: bool


_TEXT_PATTERNS: Tuple[Tuple[str, Pattern[str]], ...] = (
    (
        "certificate",
        re.compile(r"-----BEGIN CERTIFICATE-----", re.IGNORECASE),
    ),
    (
        "openai_token",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "github_token",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{16,})\b"
        ),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "authorization_header",
        re.compile(r"(?im)^\s*authorization\s*:\s*[^\r\n]+"),
    ),
    (
        "cookie_header",
        re.compile(r"(?im)^\s*(?:cookie|set-cookie)\s*[:=]\s*[^\r\n]+"),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?im)(?<![A-Za-z0-9])(?:[A-Za-z0-9]{1,32}_){0,8}"
            r"(?:password|passwd|token|secret(?:_access_key)?|"
            r"api_key|api[\s-]?key|client_secret|cookie)"
            r"\s*[:=]\s*(?:[\"'][^\"'\r\n]*[\"']|[^\s,\r\n]+)"
        ),
    ),
)
_PRIVATE_KEY_BEGIN = re.compile(
    r"-----BEGIN ((?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY)-----",
    re.IGNORECASE,
)

_PRIVATE_KEY_NAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
_CERTIFICATE_SUFFIXES = {".crt", ".cer", ".p12", ".pfx", ".pem"}
_BROWSER_PARTS = {
    "chrome",
    "chromium",
    "firefox",
    "safari",
    "edge",
    "brave",
    "browser",
}
_BROWSER_STATE_NAMES = {
    "cookies",
    "login data",
    "history",
    "web data",
    "local state",
    "preferences",
    "session storage",
}


def classify_sensitive_path(path: Path) -> PathClassification:
    """Classify a path without retaining or returning the path itself."""

    candidate = Path(path)
    name = candidate.name.lower()
    parts = {part.lower() for part in candidate.parts}
    categories = []

    if name == "auth.json":
        categories.append("auth_file")
    if name == ".env" or name.startswith(".env."):
        categories.append("environment_file")
    if (
        name in _PRIVATE_KEY_NAMES
        or candidate.suffix.lower() == ".key"
        or "private-key" in name
        or "private_key" in name
    ):
        categories.append("private_key_file")
    elif candidate.suffix.lower() in _CERTIFICATE_SUFFIXES:
        categories.append("certificate_file")
    if parts.intersection(_BROWSER_PARTS) and (
        name in _BROWSER_STATE_NAMES
        or "session" in name
        or "cookie" in name
    ):
        categories.append("browser_state")

    unique = tuple(dict.fromkeys(categories))
    return PathClassification(bool(unique), unique)


def scan_sensitive_text(text: str) -> SensitiveScan:
    """Return only matched category names, never matched values."""

    categories = []
    if _PRIVATE_KEY_BEGIN.search(text):
        categories.append("private_key")
    categories.extend(
        category for category, pattern in _TEXT_PATTERNS if pattern.search(text)
    )
    unique = tuple(dict.fromkeys(categories))
    return SensitiveScan(bool(unique), unique)


def summarize_prompt(text: str, max_bytes: int) -> PromptSummary:
    """Create a SHA-256-backed, redacted UTF-8 excerpt within ``max_bytes``."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    scan = scan_sensitive_text(text)
    redacted_text = _redact_private_keys(text)
    for category, pattern in _TEXT_PATTERNS:
        redacted_text = pattern.sub("[REDACTED:{}]".format(category), redacted_text)
    encoded = redacted_text.encode("utf-8")
    excerpt = _truncate_utf8(encoded, max_bytes)
    return PromptSummary(
        excerpt=excerpt,
        digest=digest,
        redacted=scan.is_sensitive,
        truncated=len(encoded) > max_bytes,
    )


def is_digest_only(
    *, path: Optional[Path] = None, text: Optional[str] = None
) -> bool:
    """Return whether persistence must be limited to a digest."""

    if path is not None and classify_sensitive_path(path).is_sensitive:
        return True
    return text is not None and scan_sensitive_text(text).is_sensitive


def _truncate_utf8(encoded: bytes, max_bytes: int) -> str:
    if len(encoded) <= max_bytes:
        return encoded.decode("utf-8")
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _redact_private_keys(text: str) -> str:
    parts = []
    cursor = 0
    folded_text = text.casefold()
    while True:
        match = _PRIVATE_KEY_BEGIN.search(text, cursor)
        if match is None:
            parts.append(text[cursor:])
            break
        parts.append(text[cursor : match.start()])
        end_marker = "-----END {}-----".format(match.group(1))
        end_index = folded_text.find(end_marker.casefold(), match.end())
        parts.append("[REDACTED:private_key]")
        if end_index < 0:
            break
        cursor = end_index + len(end_marker)
    return "".join(parts)
