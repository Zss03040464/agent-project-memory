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

    def test_router_feedforward_loads_profile_and_only_matching_confirmed_feedback(self) -> None:
        router = import_api("agent_project_memory.router")
        project = self.root / "workspace" / "demo"
        project.mkdir(parents=True)
        router.upsert_project_record(
            self.memory,
            router.ProjectRecord(
                project_id="demo-id",
                canonical_roots=(str(project.resolve()),),
                purpose="demo",
                authoritative_files=("AGENTS.md",),
                last_verified_at="2026-06-22T00:00:00+00:00",
            ),
        )
        (self.memory / "profile.md").write_text("Reply concisely.\n", encoding="utf-8")
        promotions = self.memory / "feedback" / "promotions"
        promotions.mkdir(parents=True)
        (promotions / "current.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "scope": "project:demo-id",
                    "normalized_intent": "run focused tests first",
                }
            ),
            encoding="utf-8",
        )
        (promotions / "other.json").write_text(
            json.dumps(
                {
                    "active": True,
                    "scope": "project:other-id",
                    "normalized_intent": "unrelated correction",
                }
            ),
            encoding="utf-8",
        )

        decision = router.route_project_memory(project, self.memory)

        self.assertIn("Reply concisely", decision.context)
        self.assertIn("run focused tests first", decision.context)
        self.assertIn("project-memory Skill", decision.context)
        self.assertNotIn("unrelated correction", decision.context)

    def test_router_recovers_new_worktree_by_repo_identity_and_refreshes_record(self) -> None:
        router = import_api("agent_project_memory.router")
        identity = import_api("agent_project_memory.identity")
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@invalid"], check=True)
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
        primary = identity.discover_git_identity(repo)
        router.upsert_project_record(
            self.memory,
            router.ProjectRecord(
                project_id="repo-id",
                canonical_roots=(str(repo.resolve()),),
                purpose="shared repository",
                authoritative_files=("AGENTS.md",),
                last_verified_at="2026-06-22T00:00:00+00:00",
                repo_id=primary.repo_id,
                worktree_id=primary.worktree_id,
            ),
        )
        second = self.root / "second-worktree"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(second), "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
        )

        decision = router.route_project_memory(second, self.memory)

        self.assertEqual(decision.project_id, "repo-id")
        self.assertIn("repository identity", decision.reason)
        record = json.loads(
            (self.memory / "projects" / "repo-id" / "record.json").read_text(encoding="utf-8")
        )
        self.assertIn(str(second.resolve()), record["canonical_roots"])
        self.assertIn(identity.discover_git_identity(second).worktree_id, record["worktree_ids"])

    def test_upsert_tracks_moved_roots_and_remote_history(self) -> None:
        router = import_api("agent_project_memory.router")
        old = self.root / "old"
        new = self.root / "new"
        old.mkdir()
        new.mkdir()
        first = router.ProjectRecord(
            project_id="moved-id",
            canonical_roots=(str(old.resolve()),),
            purpose="moved project",
            authoritative_files=("AGENTS.md",),
            last_verified_at="2026-01-01T00:00:00+00:00",
            git_remote="https://example.invalid/old.git",
        )
        router.upsert_project_record(self.memory, first)
        old.rmdir()
        router.upsert_project_record(
            self.memory,
            router.ProjectRecord(
                project_id="moved-id",
                canonical_roots=(str(new.resolve()),),
                purpose="moved project",
                authoritative_files=("AGENTS.md",),
                last_verified_at="2026-06-22T00:00:00+00:00",
                git_remote="https://example.invalid/new.git",
            ),
        )
        record = json.loads(
            (self.memory / "projects" / "moved-id" / "record.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["canonical_roots"], [str(new.resolve())])
        self.assertIn(str(old.resolve()), record["previous_roots"])
        self.assertIn("https://example.invalid/old.git", record["remote_history"])

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
        events = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(item.get("timestamp") for item in events))
        promotion_path = root / "promotions" / f"{promoted.rule_id}.json"
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        self.assertEqual(promotion["destination"], "profile-memory")
        self.assertEqual(promotion["scope"], "global")
        self.assertEqual(promotion["evidence_count"], 2)
        self.assertTrue(promotion["active"])

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
        rolled_back = json.loads(promotion_path.read_text(encoding="utf-8"))
        self.assertFalse(rolled_back["active"])
        self.assertEqual(rolled_back["rollback_reason"], "user rollback")

    def test_feedback_routes_repeatable_workflow_to_skill_artifact(self) -> None:
        feedback = import_api("agent_project_memory.feedback")
        root = self.memory / "feedback"
        first = feedback.record_feedback(
            root,
            category="workflow",
            scope="project:demo",
            session_id="s1",
            turn_id="t1",
            normalized_intent="run verification before delivery",
            evidence_pointer="turn:s1:t1",
        )
        second = feedback.record_feedback(
            root,
            category="workflow",
            scope="project:demo",
            session_id="s2",
            turn_id="t2",
            normalized_intent="run verification before delivery",
            evidence_pointer="turn:s2:t2",
        )
        self.assertFalse(first.promoted)
        self.assertTrue(second.promoted)
        promotion = json.loads(
            (root / "promotions" / f"{second.rule_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(promotion["destination"], "skill")

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

    def test_completion_gate_does_not_flag_its_own_detector_and_test_fixtures(
        self,
    ) -> None:
        gate = import_api("agent_project_memory.completion_gate")
        project = self.root / "self-hosting-project"
        (project / "src").mkdir(parents=True)
        (project / "tests").mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.email", "test@invalid"], check=True)
        (project / "任务.md").write_text("# Tasks\n", encoding="utf-8")
        (project / "交接.md").write_text("# Handoff\n", encoding="utf-8")
        (project / "src" / "privacy.py").write_text(
            'CERTIFICATE_PATTERN = "-----BEGIN CERTIFICATE-----"\n',
            encoding="utf-8",
        )
        (project / "src" / "config.py").write_text(
            "token = match.group(0)\n",
            encoding="utf-8",
        )
        (project / "tests" / "test_privacy.py").write_text(
            'password = "example-value"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(project), "add", "."], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "base"], check=True)

        result = gate.run_completion_gate(
            project,
            required_requirements=("tests",),
            evidence={"tests": True},
            expected_git_state=gate.capture_git_state(project),
        )

        self.assertTrue(result.passed)

    def test_completion_gate_flags_generic_secret_assignment_in_config_data(
        self,
    ) -> None:
        gate = import_api("agent_project_memory.completion_gate")
        project = self.root / "config-secret-project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.email", "test@invalid"], check=True)
        (project / "任务.md").write_text("# Tasks\n", encoding="utf-8")
        (project / "交接.md").write_text("# Handoff\n", encoding="utf-8")
        (project / "settings.toml").write_text(
            'api_key = "private-value"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(project), "add", "."], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "base"], check=True)

        result = gate.run_completion_gate(
            project,
            required_requirements=("tests",),
            evidence={"tests": True},
            expected_git_state=gate.capture_git_state(project),
        )

        self.assertIn("sensitive-content", result.hard_failures)


if __name__ == "__main__":
    unittest.main(verbosity=2)
