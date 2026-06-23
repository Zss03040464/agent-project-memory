from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN AGENT_PROJECT_MEMORY_RULES -->"
END = "<!-- END AGENT_PROJECT_MEMORY_RULES -->"
POSIX_SHELL_ONLY = unittest.skipIf(
    os.name == "nt", "POSIX shell installer is covered on POSIX runners"
)


def run_cmd(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )


class InstallerSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="apm-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    @POSIX_SHELL_ONLY
    def test_dry_run_does_not_write_files(self) -> None:
        target = self.tmp / ".codex"
        run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--dry-run"])
        self.assertFalse(target.exists(), "dry-run must not create the target directory")

    @POSIX_SHELL_ONLY
    def test_install_creates_expected_memory_files(self) -> None:
        target = self.tmp / ".codex"
        run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--yes"])
        self.assertTrue((target / "project_memory/INDEX.md").is_file())
        self.assertTrue((target / "project_memory/CLOUD.md").is_file())
        self.assertTrue((target / "project_memory/templates/PROJECT_SUMMARY.template.md").is_file())
        self.assertTrue((target / "project_memory/templates/ISSUE_SUMMARY.template.md").is_file())
        self.assertTrue((target / "project_memory/templates/RECOVERY.template.md").is_file())
        self.assertTrue((target / "project_memory/.agent-memory-ignore").is_file())
        self.assertTrue((target / "PROJECT_MEMORY_RULES_TO_ADD.md").is_file())

    @POSIX_SHELL_ONLY
    def test_managed_block_is_idempotent(self) -> None:
        target = self.tmp / ".codex"
        target.mkdir(parents=True)
        rules = target / "AGENTS.md"
        rules.write_text("# Existing rules\n\nKeep this line.\n", encoding="utf-8")
        for _ in range(2):
            run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--yes"])
        text = rules.read_text(encoding="utf-8")
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        self.assertIn("Keep this line.", text)

    @POSIX_SHELL_ONLY
    def test_existing_index_is_not_overwritten(self) -> None:
        target = self.tmp / ".codex"
        memory = target / "project_memory"
        memory.mkdir(parents=True)
        index = memory / "INDEX.md"
        index.write_text("# User Index\n\nDo not overwrite.\n", encoding="utf-8")
        run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--yes"])
        self.assertEqual(index.read_text(encoding="utf-8"), "# User Index\n\nDo not overwrite.\n")

    @POSIX_SHELL_ONLY
    def test_uninstall_removes_only_managed_block_by_default(self) -> None:
        target = self.tmp / ".codex"
        target.mkdir(parents=True)
        rules = target / "AGENTS.md"
        rules.write_text("# Existing rules\n", encoding="utf-8")
        run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--yes"])
        run_cmd(["bash", "installers/uninstall.sh", "--target", str(target), "--yes"])
        text = rules.read_text(encoding="utf-8")
        self.assertNotIn(BEGIN, text)
        self.assertTrue((target / "project_memory/INDEX.md").is_file())

    @POSIX_SHELL_ONLY
    def test_force_template_backs_up_existing_index(self) -> None:
        target = self.tmp / ".codex"
        memory = target / "project_memory"
        memory.mkdir(parents=True)
        index = memory / "INDEX.md"
        index.write_text("# Custom Index\n", encoding="utf-8")
        run_cmd(["bash", "installers/install-codex.sh", "--target", str(target), "--yes", "--force-template"])
        self.assertTrue(any(memory.glob("INDEX.md.backup.*")))
        self.assertIn("# Project Memory Index", index.read_text(encoding="utf-8"))

    @POSIX_SHELL_ONLY
    def test_shell_scripts_parse(self) -> None:
        scripts = [
            "installers/install-common.sh",
            "installers/install-codex.sh",
            "installers/install-claude.sh",
            "installers/install-gemini.sh",
            "installers/uninstall.sh",
            "scripts/smoke-test.sh",
        ]
        for script in scripts:
            run_cmd(["bash", "-n", script])

    def test_powershell_scripts_are_present_and_parameterized(self) -> None:
        scripts = [
            "installers/install-common.ps1",
            "installers/install-codex.ps1",
            "installers/install-claude.ps1",
            "installers/install-gemini.ps1",
            "installers/uninstall.ps1",
            "scripts/smoke-test.ps1",
        ]
        for script in scripts:
            text = (ROOT / script).read_text(encoding="utf-8")
            self.assertIn("$ErrorActionPreference", text)
        common = (ROOT / "installers/install-common.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$DryRun", common)
        self.assertIn("[switch]$Yes", common)
        self.assertIn("[string]$TargetDir", common)
        self.assertIn("[switch]$NoRules", common)
        self.assertIn("[switch]$Backup", common)
        self.assertIn("[switch]$ForceTemplate", common)


if __name__ == "__main__":
    unittest.main(verbosity=2)
