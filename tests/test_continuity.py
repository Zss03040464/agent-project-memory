from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import import_api


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def initialize_repo(path: Path) -> None:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test User")
    git(path, "config", "user.email", "test@invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-qm", "base")


def payload(
    event: str,
    cwd: Path,
    *,
    session: str = "session-a",
    turn: str = "turn-a",
    transcript: Path | None = None,
    **extra: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "hook_event_name": event,
        "cwd": str(cwd),
        "session_id": session,
        "turn_id": turn,
        "transcript_path": str(transcript) if transcript else None,
        "model": "test-model",
        "permission_mode": "default",
    }
    result.update(extra)
    return result


class ContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-continuity-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.codex_home = self.root / "codex-home"
        initialize_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_user_prompt_opens_private_turn_with_redacted_bounded_goal(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        private_value = "sk-" + ("Z" * 24)
        result = continuity.handle_hook_event(
            payload(
                "UserPromptSubmit",
                self.repo,
                prompt="continue task token=" + private_value,
            ),
            codex_home=self.codex_home,
        )
        state = json.loads(result.turn_path.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "open")
        self.assertEqual(state["session_id"], "session-a")
        self.assertEqual(state["turn_id"], "turn-a")
        self.assertEqual(len(state["prompt_digest"]), 64)
        self.assertIsNone(state["prompt_excerpt_redacted"])
        self.assertNotIn(private_value, result.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(state["last_event"], "UserPromptSubmit")
        self.assertTrue(state["requires_external_revalidation"])
        self.assertEqual(state["schema_version"], 1)
        if os.name != "nt":
            self.assertEqual(oct(result.turn_path.stat().st_mode & 0o777), "0o600")

    def test_post_tool_use_updates_evidence_without_storing_raw_tool_payload(
        self,
    ) -> None:
        continuity = import_api("agent_project_memory.continuity")
        continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="edit tracked file"),
            codex_home=self.codex_home,
        )
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        marker = "RAW-TOOL-MARKER"

        result = continuity.handle_hook_event(
            payload(
                "PostToolUse",
                self.repo,
                tool_name="functions.exec_command",
                tool_input={"command": marker},
                tool_response={"output": marker},
                tool_use_id="tool-1",
            ),
            codex_home=self.codex_home,
        )
        text = result.turn_path.read_text(encoding="utf-8")
        state = json.loads(text)

        self.assertEqual(state["status"], "open")
        self.assertEqual(state["last_completed_tool"], "shell")
        self.assertEqual(state["last_event"], "PostToolUse")
        self.assertIn("tracked.txt", state["changed_paths"])
        self.assertTrue(state["checkpoint_ref"])
        self.assertTrue(state["checkpoint_commit"])
        self.assertNotIn(marker, text)
        self.assertNotIn("tool_input", text)
        self.assertNotIn("tool_response", text)

    def test_precompact_and_stop_have_distinct_non_completion_states(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="long task"),
            codex_home=self.codex_home,
        )

        compacted = continuity.handle_hook_event(
            payload("PreCompact", self.repo, trigger="auto"),
            codex_home=self.codex_home,
        )
        compact_state = json.loads(compacted.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(compact_state["status"], "compacted")
        self.assertIsNone(compact_state["closed_at"])

        stopped = continuity.handle_hook_event(
            payload(
                "Stop",
                self.repo,
                last_assistant_message="turn ended",
                stop_hook_active=False,
            ),
            codex_home=self.codex_home,
        )
        stop_state = json.loads(stopped.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(stop_state["status"], "closed")
        self.assertTrue(stop_state["closed_at"])
        self.assertNotIn("task_complete", stop_state)

    def test_abrupt_interruption_without_posttool_or_stop_freezes_and_recovers(
        self,
    ) -> None:
        continuity = import_api("agent_project_memory.continuity")
        first = continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="change tracked file"),
            codex_home=self.codex_home,
        )
        (self.repo / "tracked.txt").write_text(
            "changed after prompt only\n", encoding="utf-8"
        )

        recovered = continuity.handle_hook_event(
            payload(
                "SessionStart",
                self.repo,
                session="session-b",
                turn="turn-b",
                source="startup",
            ),
            codex_home=self.codex_home,
        )
        state = json.loads(first.turn_path.read_text(encoding="utf-8"))
        recovery = json.loads(recovered.recovery_json.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "interrupted")
        self.assertEqual(state["last_event"], "SessionStart")
        self.assertTrue(state["checkpoint_ref"])
        self.assertTrue(state["checkpoint_commit"])
        self.assertEqual(
            git(self.repo, "show", f"{state['checkpoint_commit']}:tracked.txt"),
            "changed after prompt only",
        )
        self.assertEqual(recovery["status"], "interrupted")
        self.assertEqual(recovery["previous_session_id"], "session-a")
        self.assertEqual(recovery["new_session_id"], "session-b")
        self.assertTrue(recovered.recovery_markdown.is_file())
        self.assertIn("先读取项目规则与管理文件", recovered.additional_context)
        self.assertNotIn("changed after prompt only", recovered.additional_context)
        self.assertEqual(
            (self.repo / "tracked.txt").read_text(encoding="utf-8"),
            "changed after prompt only\n",
        )

    def test_same_session_resume_does_not_mark_turn_interrupted(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        opened = continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="continue"),
            codex_home=self.codex_home,
        )

        resumed = continuity.handle_hook_event(
            payload(
                "SessionStart",
                self.repo,
                session="session-a",
                source="resume",
            ),
            codex_home=self.codex_home,
        )
        state = json.loads(opened.turn_path.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "open")
        self.assertIsNone(resumed.recovery_json)
        self.assertEqual(resumed.additional_context, "")

    def test_new_session_interrupts_compacted_but_not_closed_turn(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        opened = continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="long task"),
            codex_home=self.codex_home,
        )
        continuity.handle_hook_event(
            payload("PreCompact", self.repo, trigger="auto"),
            codex_home=self.codex_home,
        )

        interrupted = continuity.handle_hook_event(
            payload(
                "SessionStart",
                self.repo,
                session="session-b",
                source="startup",
            ),
            codex_home=self.codex_home,
        )
        state = json.loads(opened.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "interrupted")
        self.assertTrue(interrupted.recovery_json.is_file())

        continuity.mark_recovered(opened.turn_path)
        continuity.handle_hook_event(
            payload("Stop", self.repo, session="session-b"),
            codex_home=self.codex_home,
        )
        closed_start = continuity.handle_hook_event(
            payload(
                "SessionStart",
                self.repo,
                session="session-c",
                source="startup",
            ),
            codex_home=self.codex_home,
        )
        closed = json.loads(opened.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(closed["status"], "closed")
        self.assertIsNone(closed_start.recovery_json)

    def test_checkpoint_failure_does_not_erase_turn_or_recovery_journal(
        self,
    ) -> None:
        continuity = import_api("agent_project_memory.continuity")
        with mock.patch(
            "agent_project_memory.continuity.create_git_checkpoint",
            side_effect=RuntimeError("checkpoint unavailable"),
        ):
            opened = continuity.handle_hook_event(
                payload("UserPromptSubmit", self.repo, prompt="persist goal"),
                codex_home=self.codex_home,
            )
        state = json.loads(opened.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "open")
        self.assertIsNone(state["checkpoint_commit"])

        with mock.patch(
            "agent_project_memory.continuity.create_git_checkpoint",
            side_effect=RuntimeError("checkpoint unavailable"),
        ):
            recovered = continuity.handle_hook_event(
                payload(
                    "SessionStart",
                    self.repo,
                    session="session-b",
                    source="startup",
                ),
                codex_home=self.codex_home,
            )
        interrupted = json.loads(opened.turn_path.read_text(encoding="utf-8"))
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertTrue(recovered.recovery_json.is_file())
        self.assertIn("恢复", recovered.additional_context)

    def test_session_start_only_reads_current_worktree_turn(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        second = self.root / "second"
        git(self.repo, "worktree", "add", "--detach", str(second), "HEAD")
        primary = continuity.handle_hook_event(
            payload(
                "UserPromptSubmit",
                self.repo,
                session="primary-session",
                prompt="primary",
            ),
            codex_home=self.codex_home,
        )
        other = continuity.handle_hook_event(
            payload(
                "UserPromptSubmit",
                second,
                session="other-session",
                prompt="other",
            ),
            codex_home=self.codex_home,
        )

        continuity.handle_hook_event(
            payload(
                "SessionStart",
                second,
                session="new-other-session",
                source="startup",
            ),
            codex_home=self.codex_home,
        )
        primary_state = json.loads(primary.turn_path.read_text(encoding="utf-8"))
        other_state = json.loads(other.turn_path.read_text(encoding="utf-8"))

        self.assertEqual(primary_state["status"], "open")
        self.assertEqual(other_state["status"], "interrupted")
        self.assertNotEqual(primary.turn_path.parent, other.turn_path.parent)

    def test_transcript_index_is_best_effort_and_never_copies_raw_tail(self) -> None:
        recovery = import_api("agent_project_memory.recovery")
        transcript = self.root / "session.jsonl"
        marker = "RAW-TRANSCRIPT-CONTENT"
        transcript.write_text(
            "not-json\n"
            + json.dumps(
                {
                    "type": "response_item",
                    "payload": {"kind": "tool", "content": marker},
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = recovery.index_transcript_tail(transcript)
        missing = recovery.index_transcript_tail(self.root / "missing.jsonl")

        self.assertTrue(result.exists)
        self.assertEqual(result.last_record_type, "response_item")
        self.assertNotIn(marker, repr(result))
        self.assertFalse(missing.exists)
        self.assertIsNone(missing.last_record_type)

    def test_mark_recovered_preserves_recovery_evidence(self) -> None:
        continuity = import_api("agent_project_memory.continuity")
        opened = continuity.handle_hook_event(
            payload("UserPromptSubmit", self.repo, prompt="work"),
            codex_home=self.codex_home,
        )
        continuity.handle_hook_event(
            payload(
                "SessionStart",
                self.repo,
                session="session-b",
                source="startup",
            ),
            codex_home=self.codex_home,
        )

        continuity.mark_recovered(opened.turn_path)
        state = json.loads(opened.turn_path.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "recovered")
        self.assertTrue((opened.turn_path.parent / "recovery.json").is_file())
        self.assertTrue((opened.turn_path.parent / "recovery.md").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
