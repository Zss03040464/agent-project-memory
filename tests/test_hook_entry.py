from __future__ import annotations

import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
