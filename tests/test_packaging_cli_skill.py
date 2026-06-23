from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "apm.py"), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


class PluginPackagingTests(unittest.TestCase):
    def test_manifest_uses_supported_default_discovery_shape(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "agent-project-memory")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("hooks", manifest)
        self.assertEqual(manifest["author"]["name"], "Vivian")
        interface = manifest["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "defaultPrompt",
        ):
            self.assertIn(field, interface)

    def test_default_hook_config_covers_continuity_events_portably(self) -> None:
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        hooks = config["hooks"]
        self.assertEqual(
            set(hooks),
            {"SessionStart", "UserPromptSubmit", "PostToolUse", "PreCompact", "Stop"},
        )
        for event, groups in hooks.items():
            self.assertTrue(groups, event)
            command = groups[0]["hooks"][0]
            self.assertEqual(command["type"], "command")
            self.assertIn("$PLUGIN_ROOT", command["command"])
            self.assertIn("%PLUGIN_ROOT%", command["commandWindows"])
            self.assertNotIn(str(ROOT), json.dumps(command))

    def test_hook_launcher_runs_from_unrelated_cwd_without_package_install(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-hook-package-") as raw:
            codex_home = Path(raw) / "Codex Home 空格"
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "hook-entry.py")],
                cwd=Path(raw),
                env=env,
                input=json.dumps(
                    {
                        "hook_event_name": "SessionStart",
                        "session_id": "packaging-test",
                        "source": "startup",
                        "cwd": raw,
                    }
                ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])
            self.assertTrue(output["suppressOutput"])

    def test_ci_declares_cross_platform_runtime_and_package_gates(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for required in (
            "ubuntu-latest",
            "macos-latest",
            "windows-latest",
            '"3.9"',
            '"3.14"',
            "python -m unittest discover -s tests -v",
            "scripts/smoke-test.ps1",
            "scripts/privacy_scan.py",
            "validate_plugin.py",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("PowerShell smoke test skipped", workflow)
        self.assertNotIn("if command -v pwsh", workflow)

    def test_repository_plugin_validator_accepts_current_package(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_plugin.py"), str(ROOT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Plugin validation passed", result.stdout)

    def test_public_audits_do_not_contain_machine_home_paths(self) -> None:
        for audit in (ROOT / "docs" / "audits").glob("*.md"):
            text = audit.read_text(encoding="utf-8")
            with self.subTest(audit=audit.name):
                self.assertNotIn("/Users/", text)
                self.assertNotIn("C:\\Users\\", text)


class CliAndSkillTests(unittest.TestCase):
    def test_cli_routes_only_the_current_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-cli-") as raw:
            root = Path(raw)
            project = root / "工作 空间" / "demo"
            project.mkdir(parents=True)
            memory = root / "memory"
            run_cli(
                "project",
                "upsert",
                "--memory-root",
                str(memory),
                "--project-id",
                "demo-id",
                "--root",
                str(project),
                "--purpose",
                "demo purpose",
                "--authoritative-file",
                "AGENTS.md",
                "--verified-at",
                "2026-06-22T00:00:00+00:00",
            )
            result = run_cli(
                "route",
                "--memory-root",
                str(memory),
                "--cwd",
                str(project),
                "--json",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["project_id"], "demo-id")
            self.assertEqual(payload["loaded_records"], ["demo-id"])
            self.assertIn("canonical root", payload["reason"])

    def test_cli_feedback_promotes_only_after_two_distinct_turns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-feedback-cli-") as raw:
            root = Path(raw)
            common = (
                "feedback",
                "record",
                "--root",
                str(root),
                "--category",
                "language",
                "--scope",
                "global",
                "--intent",
                "reply in Chinese",
                "--evidence",
                "turn",
                "--json",
            )
            first = json.loads(
                run_cli(*common, "--session-id", "s1", "--turn-id", "t1").stdout
            )
            second = json.loads(
                run_cli(*common, "--session-id", "s2", "--turn-id", "t2").stdout
            )
            self.assertFalse(first["promoted"])
            self.assertTrue(second["promoted"])
            self.assertEqual(second["distinct_evidence_count"], 2)

    def test_cli_gate_returns_nonzero_for_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-gate-cli-") as raw:
            root = Path(raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@invalid"], check=True)
            (root / "任务.md").write_text("# Tasks\n", encoding="utf-8")
            (root / "交接.md").write_text("# Handoff\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
            result = run_cli(
                "gate",
                "--project-root",
                str(root),
                "--require",
                "tests",
                "--json",
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("missing-evidence:tests", json.loads(result.stdout)["hard_failures"])
            passed = run_cli(
                "gate",
                "--project-root",
                str(root),
                "--require",
                "tests",
                "--evidence",
                "tests",
                "--json",
                check=False,
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

    def test_cli_gate_detects_git_pollution_against_saved_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-gate-baseline-") as raw:
            root = Path(raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@invalid"], check=True)
            (root / "任务.md").write_text("# Tasks\n", encoding="utf-8")
            (root / "交接.md").write_text("# Handoff\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
            baseline = root / ".git" / "apm-baseline.json"
            run_cli(
                "snapshot",
                "--project-root",
                str(root),
                "--output",
                str(baseline),
            )
            (root / "unexpected.txt").write_text("pollution\n", encoding="utf-8")
            result = run_cli(
                "gate",
                "--project-root",
                str(root),
                "--baseline",
                str(baseline),
                "--json",
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("git-state-pollution", json.loads(result.stdout)["hard_failures"])

    def test_cli_gate_supports_unborn_repository_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="apm-gate-unborn-") as raw:
            root = Path(raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "任务.md").write_text("# Tasks\n", encoding="utf-8")
            (root / "交接.md").write_text("# Handoff\n", encoding="utf-8")
            baseline = root / ".git" / "apm-baseline.json"

            snapshot = run_cli(
                "snapshot",
                "--project-root",
                str(root),
                "--output",
                str(baseline),
                check=False,
            )
            self.assertEqual(snapshot.returncode, 0, snapshot.stdout + snapshot.stderr)
            passed = run_cli(
                "gate",
                "--project-root",
                str(root),
                "--require",
                "docs",
                "--evidence",
                "docs",
                "--baseline",
                str(baseline),
                "--json",
                check=False,
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

            (root / "unexpected.txt").write_text("pollution\n", encoding="utf-8")
            failed = run_cli(
                "gate",
                "--project-root",
                str(root),
                "--baseline",
                str(baseline),
                "--json",
                check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertIn(
                "git-state-pollution", json.loads(failed.stdout)["hard_failures"]
            )

    def test_skill_has_discovery_frontmatter_and_layered_workflow(self) -> None:
        text = (ROOT / "skills" / "project-memory" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(text.startswith("---\nname: project-memory\n"))
        self.assertIn("description: Use when", text)
        for phrase in (
            "Memory",
            "Skill",
            "Profile",
            "continuity",
            "at least 2",
            "completion gate",
            "exact project",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("Before acting, read the local project memory index", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
