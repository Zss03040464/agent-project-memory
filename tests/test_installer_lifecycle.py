from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "installers" / "install-codex.sh"
UNINSTALL = ROOT / "installers" / "uninstall.sh"
BEGIN = "<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstallerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="apm-lifecycle-"))
        self.home = self.tmp / "Home 空格"
        self.target = self.home / ".codex"
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["CODEX_HOME"] = str(self.target)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(
        self, *args: str, check: bool = True, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALL), *args],
            cwd=ROOT,
            env=env or self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=check,
        )

    def run_uninstall(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(UNINSTALL), *args],
            cwd=ROOT,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )

    def test_help_lists_all_lifecycle_operations(self) -> None:
        output = self.run_install("--help").stdout
        for word in ("install", "upgrade", "uninstall", "rollback", "--dry-run", "--backup"):
            self.assertIn(word, output)

    def test_powershell_wrapper_maps_native_parameters_to_lifecycle_cli(self) -> None:
        text = (ROOT / "installers" / "install-codex.ps1").read_text(encoding="utf-8")
        for token in (
            "param(",
            "$Operation",
            "$TargetDir",
            "$DryRun",
            "$Backup",
            "$MigrateV1Hook",
            '"--dry-run"',
            '"--migrate-v1-hook"',
            "Get-Command python3",
        ):
            self.assertIn(token, text)

    def test_install_activates_plugin_skill_cli_and_private_state(self) -> None:
        self.run_install("install", "--yes", "--backup")
        source = self.home / "plugins" / "agent-project-memory"
        marketplace = self.home / ".agents" / "plugins" / "marketplace.json"
        self.assertTrue((source / ".codex-plugin" / "plugin.json").is_file())
        self.assertTrue((source / "hooks" / "hooks.json").is_file())
        self.assertTrue((source / "skills" / "project-memory" / "SKILL.md").is_file())
        self.assertTrue((self.target / "bin" / "agent-project-memory").is_file())
        self.assertTrue((self.target / "project_memory" / "INDEX.md").is_file())
        self.assertTrue((self.target / "continuity" / "config.toml").is_file())
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.target / "continuity").stat().st_mode & 0o777, 0o700)
        catalog = json.loads(marketplace.read_text(encoding="utf-8"))
        entry = next(item for item in catalog["plugins"] if item["name"] == "agent-project-memory")
        self.assertEqual(entry["source"]["path"], "./plugins/agent-project-memory")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        listed = subprocess.run(
            ["codex", "plugin", "list", "--json"],
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        installed = json.loads(listed.stdout)["installed"]
        self.assertTrue(any(item["pluginId"] == "agent-project-memory@personal" for item in installed))
        backup_roots = list((self.target / "backups" / "agent-project-memory").glob("*"))
        self.assertTrue(any((path / "manifest.json").is_file() for path in backup_roots))

    def test_repeated_install_and_upgrade_preserve_custom_content(self) -> None:
        self.target.mkdir(parents=True)
        agents = self.target / "AGENTS.md"
        agents.write_text("# User rules\n\nKeep me.\n", encoding="utf-8")
        self.run_install("install", "--yes")
        source = self.home / "plugins" / "agent-project-memory"
        custom = source / "LOCAL-NOTES.md"
        custom.write_text("custom\n", encoding="utf-8")
        self.run_install("upgrade", "--yes")
        self.run_install("upgrade", "--yes")
        text = agents.read_text(encoding="utf-8")
        self.assertEqual(text.count(BEGIN), 1)
        self.assertIn("Keep me.", text)
        self.assertEqual(custom.read_text(encoding="utf-8"), "custom\n")

    def test_v1_hook_migration_removes_only_duplicate_entry_and_keeps_script(self) -> None:
        hooks_dir = self.target / "hooks"
        hooks_dir.mkdir(parents=True)
        old_script = hooks_dir / "git_checkpoint.py"
        old_script.write_text("# legacy\n", encoding="utf-8")
        hooks = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"/usr/bin/python3 {old_script}",
                            },
                            {"type": "command", "command": "printf unrelated"},
                        ]
                    }
                ]
            }
        }
        (self.target / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
        self.run_install("install", "--yes", "--migrate-v1-hook", "--backup")
        updated = json.loads((self.target / "hooks.json").read_text(encoding="utf-8"))
        commands = [
            item["command"]
            for group in updated["hooks"]["Stop"]
            for item in group["hooks"]
        ]
        self.assertEqual(commands, ["printf unrelated"])
        self.assertTrue(old_script.is_file())
        manifests = list(
            (self.target / "backups" / "agent-project-memory").glob("*/manifest.json")
        )
        self.assertTrue(any("hooks.json" in path.read_text(encoding="utf-8") for path in manifests))

    def test_failure_rolls_back_existing_files_and_does_not_leave_plugin(self) -> None:
        self.target.mkdir(parents=True)
        agents = self.target / "AGENTS.md"
        agents.write_text("# Untouched\n", encoding="utf-8")
        before = digest(agents)
        env = self.env.copy()
        env["APM_INSTALLER_TEST_FAIL"] = "after-marketplace"
        result = self.run_install("install", "--yes", check=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(digest(agents), before)
        self.assertFalse((self.home / "plugins" / "agent-project-memory").exists())
        self.assertFalse((self.home / ".agents" / "plugins" / "marketplace.json").exists())

    def test_uninstall_keeps_memory_and_rollback_restores_install(self) -> None:
        self.run_install("install", "--yes", "--backup")
        memory = self.target / "project_memory" / "INDEX.md"
        memory.write_text("# User memory\n", encoding="utf-8")
        self.run_uninstall("--yes")
        self.assertEqual(memory.read_text(encoding="utf-8"), "# User memory\n")
        self.assertFalse((self.home / "plugins" / "agent-project-memory").exists())
        self.assertFalse((self.target / "bin" / "agent-project-memory").exists())
        self.run_install("rollback", "--yes")
        self.assertTrue((self.home / "plugins" / "agent-project-memory").is_dir())
        self.assertTrue((self.target / "bin" / "agent-project-memory").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
