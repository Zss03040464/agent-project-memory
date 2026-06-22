from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import import_api


class RouterFeedbackGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-control-")
        self.root = Path(self.tmp.name)
        self.memory = self.root / "project_memory"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_router_loads_only_exact_current_project_and_explains_decision(self) -> None:
        router = import_api("agent_project_memory.router")
        first = self.root / "workspace" / "first"
        second = self.root / "workspace" / "second"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        router.upsert_project_record(
            self.memory,
            router.ProjectRecord(
                project_id="first-id",
                canonical_roots=(str(first.resolve()),),
                purpose="first project",
                authoritative_files=("AGENTS.md", "交接.md"),
                last_verified_at="2026-06-22T00:00:00+00:00",
            ),
        )
        router.upsert_project_record(
            self.memory,
            router.ProjectRecord(
                project_id="second-id",
                canonical_roots=(str(second.resolve()),),
                purpose="second project",
                authoritative_files=("AGENTS.md",),
                last_verified_at="2026-06-22T00:00:00+00:00",
            ),
        )

        decision = router.route_project_memory(first / "src", self.memory)

        self.assertEqual(decision.project_id, "first-id")
        self.assertEqual(decision.loaded_records, ("first-id",))
        self.assertEqual(decision.skipped_records, ("second-id",))
        self.assertIn("canonical root", decision.reason)
        self.assertNotIn("second project", decision.context)
        index = (self.memory / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("first-id", index)
        self.assertIn("second-id", index)
        self.assertNotIn("first project", index)

    def test_feedback_requires_two_distinct_turns_and_conflict_blocks_promotion(self) -> None:
        feedback = import_api("agent_project_memory.feedback")
        root = self.memory / "feedback"
        one = feedback.record_feedback(
            root,
            category="language",
            scope="global",
            session_id="s1",
            turn_id="t1",
            normalized_intent="reply in Chinese",
            evidence_pointer="turn:s1:t1",
        )
        duplicate = feedback.record_feedback(
            root,
            category="language",
            scope="global",
            session_id="s1",
            turn_id="t1",
            normalized_intent="reply in Chinese",
            evidence_pointer="turn:s1:t1",
        )
        promoted = feedback.record_feedback(
            root,
            category="language",
            scope="global",
            session_id="s2",
            turn_id="t2",
            normalized_intent="reply in Chinese",
            evidence_pointer="turn:s2:t2",
        )

        self.assertFalse(one.promoted)
        self.assertFalse(duplicate.promoted)
        self.assertTrue(promoted.promoted)
        self.assertEqual(promoted.distinct_evidence_count, 2)
        learned = (root / "learned-rules.md").read_text(encoding="utf-8")
        self.assertIn("reply in Chinese", learned)

        conflict = feedback.record_feedback(
            root,
            category="language",
            scope="global",
            session_id="s3",
            turn_id="t3",
            normalized_intent="reply in English",
            evidence_pointer="turn:s3:t3",
            conflict=True,
        )
        self.assertFalse(conflict.promoted)
        self.assertTrue(conflict.blocked_by_conflict)
        feedback.rollback_promotion(root, promoted.rule_id, reason="user rollback")
        self.assertIn("rolled back", (root / "learned-rules.md").read_text(encoding="utf-8"))

    def test_feedback_scope_isolated_between_projects(self) -> None:
        feedback = import_api("agent_project_memory.feedback")
        root = self.memory / "feedback"
        for scope, session in (("project:a", "s1"), ("project:b", "s2")):
            result = feedback.record_feedback(
                root,
                category="test-command",
                scope=scope,
                session_id=session,
                turn_id="t",
                normalized_intent="run make test",
                evidence_pointer=session,
            )
            self.assertFalse(result.promoted)

    def test_completion_gate_hard_fails_missing_evidence_secrets_and_git_pollution(
        self,
    ) -> None:
        gate = import_api("agent_project_memory.completion_gate")
        project = self.root / "project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.email", "test@invalid"], check=True)
        (project / "任务.md").write_text("# Tasks\n", encoding="utf-8")
        (project / "交接.md").write_text("# Handoff\n", encoding="utf-8")
        (project / "safe.txt").write_text("safe\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "."], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "base"], check=True)
        baseline = gate.capture_git_state(project)
        (project / ".env").write_text("PASSWORD=private-value\n", encoding="utf-8")

        failed = gate.run_completion_gate(
            project,
            required_requirements=("tests", "handoff"),
            evidence={"tests": False, "handoff": True},
            expected_git_state=baseline,
        )
        self.assertFalse(failed.passed)
        self.assertIn("missing-evidence:tests", failed.hard_failures)
        self.assertIn("sensitive-content", failed.hard_failures)
        self.assertIn("git-state-pollution", failed.hard_failures)

        (project / ".env").unlink()
        passed = gate.run_completion_gate(
            project,
            required_requirements=("tests", "handoff"),
            evidence={"tests": True, "handoff": True},
            expected_git_state=gate.capture_git_state(project),
        )
        self.assertTrue(passed.passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
