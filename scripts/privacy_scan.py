from __future__ import annotations

import re
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable, List, NamedTuple


ROOT = Path(__file__).resolve().parents[1]
MAX_MEMBER_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_BINARY_METADATA_BYTES = 1024 * 1024

FORBIDDEN_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "authorization_header": re.compile(
        r"(?im)^\s*Authorization\s*:\s*(?:Bearer|Basic)\s+\S+"
    ),
}

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".conf",
    ".config",
    ".csv",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
ARCHIVE_SUFFIXES = (".zip", ".whl", ".tar", ".tar.gz", ".tgz")
SENSITIVE_MEMBER_NAMES = {
    ".env",
    "auth.json",
    "credentials",
    "cookies",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_MEMBER_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


class Finding(NamedTuple):
    path: str
    category: str
    location: str


def _matches(text: str, path: str, location: str) -> List[Finding]:
    return [
        Finding(path, category, location)
        for category, pattern in FORBIDDEN_PATTERNS.items()
        if pattern.search(text)
    ]


def _sensitive_member(name: str) -> bool:
    basename = Path(name.replace("\\", "/")).name.casefold()
    return (
        basename == ".env"
        or basename.startswith(".env.")
        or basename in SENSITIVE_MEMBER_NAMES
        or basename.startswith(("credentials", "secrets", "cookie"))
        or basename.endswith(SENSITIVE_MEMBER_SUFFIXES)
    )


def _text_member(name: str) -> bool:
    return Path(name).suffix.casefold() in TEXT_SUFFIXES


def _scan_zip(path: Path, relative: str) -> List[Finding]:
    findings: List[Finding] = []
    total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if _sensitive_member(info.filename):
                    findings.append(Finding(relative, "sensitive_archive_member", "archive-listing"))
                if info.file_size > MAX_MEMBER_BYTES or not _text_member(info.filename):
                    continue
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    break
                text = archive.read(info).decode("utf-8", "ignore")
                findings.extend(_matches(text, relative, "archive-text"))
    except (OSError, RuntimeError, zipfile.BadZipFile):
        pass
    return findings


def _scan_tar(path: Path, relative: str) -> List[Finding]:
    findings: List[Finding] = []
    total = 0
    try:
        with tarfile.open(path, "r:*") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                if _sensitive_member(member.name):
                    findings.append(Finding(relative, "sensitive_archive_member", "archive-listing"))
                if member.size > MAX_MEMBER_BYTES or not _text_member(member.name):
                    continue
                total += member.size
                if total > MAX_ARCHIVE_BYTES:
                    break
                stream = archive.extractfile(member)
                if stream is not None:
                    findings.extend(
                        _matches(stream.read(MAX_MEMBER_BYTES).decode("utf-8", "ignore"), relative, "archive-text")
                    )
    except (OSError, tarfile.TarError):
        pass
    return findings


def _is_archive(path: Path) -> bool:
    folded = path.name.casefold()
    return any(folded.endswith(suffix) for suffix in ARCHIVE_SUFFIXES)


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def scan_root(root: Path) -> List[Finding]:
    base = Path(root)
    findings: List[Finding] = []
    for path in _iter_files(base):
        relative = str(path.relative_to(base))
        if _is_archive(path):
            if path.name.casefold().endswith((".zip", ".whl")):
                findings.extend(_scan_zip(path, relative))
            else:
                findings.extend(_scan_tar(path, relative))
            continue
        try:
            if path.suffix.casefold() in TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8", errors="ignore")
                findings.extend(_matches(text, relative, "text"))
            else:
                data = path.read_bytes()[:MAX_BINARY_METADATA_BYTES]
                findings.extend(_matches(data.decode("latin-1", "ignore"), relative, "binary-metadata"))
        except OSError:
            continue
    return sorted(set(findings))


def print_findings(findings: Iterable[Finding]) -> None:
    items = list(findings)
    if not items:
        print("No sensitive content patterns found.")
        return
    print("Potential sensitive content found (matched values suppressed):")
    for finding in items:
        print("- {}: {} [{}]".format(finding.path, finding.category, finding.location))


def main() -> int:
    findings = scan_root(ROOT)
    print_findings(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
