#!/usr/bin/env python3
"""Validate the repository's dependency-free Codex plugin package."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List


SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_INTERFACE = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "defaultPrompt",
}
EVENTS = {"SessionStart", "UserPromptSubmit", "PostToolUse", "PreCompact", "Stop"}


def validate(root: Path) -> List[str]:
    errors: List[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["plugin manifest is missing or invalid"]
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        errors.append("plugin name must be lower-case hyphen-case")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("plugin version must be strict semantic versioning")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        errors.append("plugin description is required")
    if not isinstance(manifest.get("author"), dict) or not manifest["author"].get("name"):
        errors.append("author.name is required")
    if "hooks" in manifest:
        errors.append("unsupported top-level hooks field must be omitted")
    if manifest.get("skills") != "./skills/":
        errors.append("skills must use ./skills/")
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("interface is required")
    else:
        missing = REQUIRED_INTERFACE - set(interface)
        if missing:
            errors.append("interface fields are missing")
        prompts = interface.get("defaultPrompt")
        if isinstance(prompts, list) and (len(prompts) > 3 or any(len(str(item)) > 128 for item in prompts)):
            errors.append("default prompts exceed interface limits")
        for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
            value = interface.get(field)
            if value is not None and (not isinstance(value, str) or not value.startswith("https://")):
                errors.append(field + " must be an absolute HTTPS URL")
    if "[TODO:" in manifest_path.read_text(encoding="utf-8"):
        errors.append("manifest contains a TODO placeholder")
    _validate_skills(root, errors)
    _validate_hooks(root, errors)
    return errors


def _validate_skills(root: Path, errors: List[str]) -> None:
    skills = list((root / "skills").glob("*/SKILL.md"))
    if not skills:
        errors.append("at least one Skill is required")
        return
    for path in skills:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\nname: " not in text[:1024] or "\ndescription: " not in text[:1024]:
            errors.append("Skill frontmatter is missing")


def _validate_hooks(root: Path, errors: List[str]) -> None:
    path = root / "hooks" / "hooks.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("default hooks/hooks.json is missing or invalid")
        return
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or set(hooks) != EVENTS:
        errors.append("continuity Hook events are incomplete")
        return
    for event, groups in hooks.items():
        if not isinstance(groups, list) or not groups:
            errors.append(event + " has no handlers")
            continue
        for group in groups:
            for handler in group.get("hooks", []):
                if handler.get("type") != "command":
                    errors.append(event + " contains an unsupported handler")
                if "$PLUGIN_ROOT" not in handler.get("command", ""):
                    errors.append(event + " Unix command is not plugin-relative")
                if "%PLUGIN_ROOT%" not in handler.get("commandWindows", ""):
                    errors.append(event + " Windows command is not plugin-relative")


def main(argv: List[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").expanduser().resolve()
    errors = validate(root)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print("- " + error)
        return 1
    print("Plugin validation passed: " + str(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
