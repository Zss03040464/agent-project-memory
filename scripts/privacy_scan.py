from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
TEXT_SUFFIXES = {".md", ".txt", ".ps1", ".sh", ".py", ".yml", ".yaml", ""}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def main() -> int:
    findings = []
    for path in iter_text_files(ROOT):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                findings.append((str(path.relative_to(ROOT)), name))

    if findings:
        print("Potential sensitive content found:")
        for file, kind in findings:
            print(f"- {file}: {kind}")
        return 1

    print("No sensitive content patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
