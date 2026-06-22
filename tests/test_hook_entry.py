from __future__ import annotations

import json
import tempfile
import unittest
import dataclasses
from pathlib import Path
from unittest import mock

from tests.helpers import import_api
from tests.test_continuity import initialize_repo, payload


class HookEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-hook-entry-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.codex_home = self.root / "codex-home"
        initialize_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_session_start_returns_official_structured_additional_context(
        self,
    ) -> None:
        hook_entry = import_api("agent_project_memory.hook_entry")
        continuity = import_api("agent_project_memory.continuity")
        continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="work"),
            codex_home=self.codex_home,
        )

        output = hook_entry.handle_payload(
            payload(
                "SessionStart",
                self.repo,
                session="new-session",
                source="startup",
            ),
            codex_home=self.codex_home,
        )

        self.assertTrue(output["continue"])
        self.assertTrue(output["suppressOutput"])
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "SessionStart")
        self.assertIn("恢复", specific["additionalContext"])

    def test_stop_and_other_events_return_valid_non_blocking_output(self) -> None:
        hook_entry = import_api("agent_project_memory.hook_entry")
        for event in ("UserPromptSubmit", "PostToolUse", "PreCompact", "Stop"):
            with self.subTest(event=event):
                extra: dict[str, object] = {}
                if event == "UserPromptSubmit":
                    extra["prompt"] = "work"
                elif event == "PostToolUse":
                    extra.update(
                        tool_name="apply_patch",
                        tool_input={},
                        tool_response={},
                        tool_use_id="tool",
                    )
                elif event == "PreCompact":
                    extra["trigger"] = "manual"
                elif event == "Stop":
                    extra.update(
                        last_assistant_message=None, stop_hook_active=False
                    )
                output = hook_entry.handle_payload(
                    payload(event, self.repo, **extra),
                    codex_home=self.codex_home,
                )
                self.assertTrue(output["continue"])
                self.assertTrue(output["suppressOutput"])
                self.assertNotIn("decision", output)

    def test_user_prompt_submit_injects_only_exact_project_memory(self) -> None:
        hook_entry = import_api("agent_project_memory.hook_entry")
        router = import_api("agent_project_memory.router")
        other = self.root / "other"
        other.mkdir()
        memory = self.codex_home / "project_memory"
        router.upsert_project_record(
            memory,
            router.ProjectRecord(
                project_id="current-project",
                canonical_roots=(str(self.repo.resolve()),),
                purpose="continue the matching project safely",
                authoritative_files=("AGENTS.md", "任务.md"),
                last_verified_at="2026-06-22T00:00:00+00:00",
            ),
        )
        router.upsert_project_record(
            memory,
            router.ProjectRecord(
                project_id="unrelated-project",
                canonical_roots=(str(other.resolve()),),
                purpose="unrelated private context",
                authoritative_files=("AGENTS.md",),
                last_verified_at="2026-06-22T00:00:00+00:00",
            ),
        )

        output = hook_entry.handle_payload(
            payload("UserPromptSubmit", self.repo, prompt="continue"),
            codex_home=self.codex_home,
        )

        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "UserPromptSubmit")
        self.assertIn("continue the matching project safely", specific["additionalContext"])
        self.assertNotIn("unrelated private context", specific["additionalContext"])

    def test_hook_failure_fails_open_without_error_or_payload_leak(self) -> None:
        hook_entry = import_api("agent_project_memory.hook_entry")
        marker = "PRIVATE-HOOK-PAYLOAD"
        with mock.patch(
            "agent_project_memory.hook_entry.handle_hook_event",
            side_effect=RuntimeError(marker),
        ):
            output = hook_entry.handle_payload(
                payload("UserPromptSubmit", self.repo, prompt=marker),
                codex_home=self.codex_home,
            )

        rendered = json.dumps(output)
        self.assertEqual(
            output, {"continue": True, "suppressOutput": True}
        )
        self.assertNotIn(marker, rendered)

    def test_hook_automatically_bootstraps_trusted_marked_project(self) -> None:
        hook_entry = import_api("agent_project_memory.hook_entry")
        config_mod = import_api("agent_project_memory.config")
        project = self.root / "Workspace" / "code" / "new-project"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            "[project]\nname='demo'\n", encoding="utf-8"
        )
        config = dataclasses.replace(
            config_mod.Config.defaults(),
            trusted_roots=((self.root / "Workspace" / "code").resolve(),),
        )

        with mock.patch(
            "agent_project_memory.hook_entry.load_config",
            return_value=config_mod.ConfigLoadResult(config),
        ):
            output = hook_entry.handle_payload(
                payload(
                    "UserPromptSubmit",
                    project,
                    prompt="start project",
                ),
                codex_home=self.codex_home,
            )

        self.assertTrue(output["continue"])
        self.assertTrue((project / ".git").is_dir())
        self.assertTrue(list((self.codex_home / "continuity" / "repos").rglob("turn.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
