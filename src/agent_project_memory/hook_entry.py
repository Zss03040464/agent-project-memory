"""Codex command-hook entrypoint with fail-open output."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

from .bootstrap import bootstrap_project
from .config import load_config
from .continuity import handle_hook_event
from .privacy import scan_sensitive_text
from .router import route_project_memory


def handle_payload(
    payload: Mapping[str, Any], *, codex_home: Path
) -> Dict[str, Any]:
    """Return an official non-blocking Hook output object."""

    try:
        cwd = Path(str(payload.get("cwd") or "."))
        config_result = load_config(
            Path(codex_home) / "continuity" / "config.toml"
        )
        bootstrap_project(
            cwd, config=config_result.config, codex_home=Path(codex_home)
        )
        result = handle_hook_event(payload, codex_home=Path(codex_home))
        output: Dict[str, Any] = {
            "continue": True,
            "suppressOutput": True,
        }
        contexts = []
        if result.event == "SessionStart" and result.additional_context:
            contexts.append(result.additional_context)
        if result.event in ("SessionStart", "UserPromptSubmit"):
            route = route_project_memory(
                cwd, Path(codex_home) / "project_memory"
            )
            if route.context and not scan_sensitive_text(
                route.context
            ).is_sensitive:
                contexts.append(route.context)
        additional_context = _bounded_context("\n\n".join(contexts), 8192)
        if additional_context:
            output["hookSpecificOutput"] = {
                "hookEventName": result.event,
                "additionalContext": additional_context,
            }
        return output
    except Exception:
        return {"continue": True, "suppressOutput": True}


def _bounded_context(value: str, limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    return encoded[:limit].decode("utf-8", "ignore")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    codex_home = Path(
        os.environ.get("CODEX_HOME") or Path.home() / ".codex"
    )
    print(
        json.dumps(
            handle_payload(payload, codex_home=codex_home),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
