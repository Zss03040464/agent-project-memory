from __future__ import annotations

import dataclasses
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import import_api


def git(cwd: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-bootstrap-")
        self.root = Path(self.tmp.name)
        self.trusted = self.root / "Workspace" / "code"
        self.trusted.mkdir(parents=True)
        self.codex_home = self.root / ".codex-state"
        config_mod = import_api("agent_project_memory.config")
        self.config = dataclasses.replace(
            config_mod.Config.defaults(),
            trusted_roots=(self.trusted.resolve(),),
            denied_roots=(
                self.codex_home.resolve(),
                (self.root / "Downloads").resolve(),
            ),
            project_markers=(
                "AGENTS.md",
                "pyproject.toml",
                "package.json",
                "Cargo.toml",
                "go.mod",
                ".project-memory.toml",
            ),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_existing_git_project_is_used_without_mutation(self) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.trusted / "existing"
        project.mkdir()
        git(project, "init", "-q")
        before = git(project, "status", "--porcelain=v2")

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )

        self.assertEqual(result.mode, "git")
        self.assertFalse(result.initialized_git)
        self.assertEqual(before, git(project, "status", "--porcelain=v2"))

    def test_marked_trusted_project_is_initialized_without_commit_or_remote(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.trusted / "marked"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            "[project]\nname='demo'\n", encoding="utf-8"
        )
        (project / "notes.txt").write_text("work\n", encoding="utf-8")

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )

        self.assertEqual(result.mode, "git")
        self.assertTrue(result.initialized_git)
        self.assertTrue((project / ".git").is_dir())
        self.assertTrue((project / ".gitignore").is_file())
        self.assertNotEqual(
            subprocess.run(
                ["git", "-C", str(project), "rev-parse", "--verify", "HEAD"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode,
            0,
        )
        self.assertEqual(git(project, "remote"), "")

    def test_empty_dedicated_directory_under_trusted_root_is_initialized(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.trusted / "new-empty-project"
        project.mkdir()

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )

        self.assertEqual(result.mode, "git")
        self.assertTrue(result.initialized_git)
        self.assertTrue((project / ".git").is_dir())

    def test_marked_non_git_outside_trusted_root_uses_external_checkpoint(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.root / "Documents" / "legacy-project"
        project.mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (project / "work.txt").write_text("recover me\n", encoding="utf-8")

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )

        self.assertEqual(result.mode, "external")
        self.assertFalse((project / ".git").exists())
        self.assertTrue(result.checkpoint_commit)
        self.assertTrue(result.external_git_dir.is_dir())
        stored = subprocess.run(
            [
                "git",
                f"--git-dir={result.external_git_dir}",
                "show",
                f"{result.checkpoint_commit}:work.txt",
            ],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        self.assertEqual(stored, "recover me\n")

    def test_dangerous_roots_are_excluded_without_scanning_or_initializing(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        downloads = self.root / "Downloads"
        downloads.mkdir()
        broad_home = self.root
        for path in (broad_home, downloads, self.codex_home):
            path.mkdir(parents=True, exist_ok=True)
            with self.subTest(path=path.name):
                result = bootstrap.bootstrap_project(
                    path, config=self.config, codex_home=self.codex_home
                )
                self.assertEqual(result.mode, "excluded")
                self.assertFalse((path / ".git").exists())
                self.assertEqual(result.scanned_files, 0)

    def test_marker_ancestor_is_selected_but_symlink_escape_is_excluded(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.trusted / "nested-project"
        child = project / "src" / "module"
        child.mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")

        found = bootstrap.identify_project_root(child, config=self.config)
        self.assertEqual(found.root, project.resolve())

        outside = self.root / "outside"
        outside.mkdir()
        (outside / "AGENTS.md").write_text("# Outside\n", encoding="utf-8")
        link = self.trusted / "escape"
        link.symlink_to(outside, target_is_directory=True)
        escaped = bootstrap.bootstrap_project(
            link, config=self.config, codex_home=self.codex_home
        )
        self.assertEqual(escaped.mode, "external")
        self.assertFalse((outside / ".git").exists())

    def test_external_checkpoint_filters_sensitive_and_generated_files(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.root / "Documents" / "filtered"
        project.mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (project / "safe.txt").write_text("safe\n", encoding="utf-8")
        (project / ".env").write_text("PASSWORD=private\n", encoding="utf-8")
        (project / "node_modules").mkdir()
        (project / "node_modules/pkg.js").write_text("generated\n", encoding="utf-8")

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )
        paths = subprocess.run(
            [
                "git",
                f"--git-dir={result.external_git_dir}",
                "ls-tree",
                "-r",
                "--name-only",
                result.checkpoint_commit,
            ],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.splitlines()

        self.assertIn("safe.txt", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("node_modules/pkg.js", paths)

    def test_broad_ancestor_marker_does_not_turn_home_tree_into_project(
        self,
    ) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        fake_home = self.root / "home"
        child = fake_home / "misc" / "folder"
        child.mkdir(parents=True)
        (fake_home / "AGENTS.md").write_text("# Global-like rules\n", encoding="utf-8")

        with mock.patch(
            "agent_project_memory.config.Path.home",
            return_value=fake_home.resolve(),
        ):
            found = bootstrap.identify_project_root(child, config=self.config)

        self.assertEqual(found.kind, "excluded")
        self.assertTrue(found.dangerous)

    def test_parent_with_nested_git_is_not_automatically_initialized(self) -> None:
        bootstrap = import_api("agent_project_memory.bootstrap")
        project = self.trusted / "contains-nested-repo"
        nested = project / "vendor" / "component"
        nested.mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Parent rules\n", encoding="utf-8")
        git(nested, "init", "-q")

        result = bootstrap.bootstrap_project(
            project, config=self.config, codex_home=self.codex_home
        )

        self.assertEqual(result.mode, "external")
        self.assertFalse((project / ".git").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
