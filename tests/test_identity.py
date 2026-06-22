from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import import_api


def git(cwd: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


class GitIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-identity-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test User")
        git(self.repo, "config", "user.email", "test@invalid")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "tracked.txt")
        git(self.repo, "commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_two_worktrees_share_repo_identity_but_not_worktree_identity(
        self,
    ) -> None:
        identity = import_api("agent_project_memory.identity")
        second = self.root / "second"
        git(self.repo, "worktree", "add", "--detach", str(second), "HEAD")

        primary_id = identity.discover_git_identity(self.repo)
        second_id = identity.discover_git_identity(second)

        self.assertEqual(primary_id.repo_id, second_id.repo_id)
        self.assertNotEqual(primary_id.worktree_id, second_id.worktree_id)
        self.assertEqual(primary_id.common_dir, second_id.common_dir)
        self.assertNotEqual(primary_id.git_dir, second_id.git_dir)
        self.assertEqual(primary_id.worktree_root, self.repo.resolve())
        self.assertEqual(second_id.worktree_root, second.resolve())

    def test_worktree_identity_survives_branch_switch_and_detached_head(
        self,
    ) -> None:
        identity = import_api("agent_project_memory.identity")
        before = identity.discover_git_identity(self.repo)
        git(self.repo, "switch", "-qc", "feature")
        on_branch = identity.discover_git_identity(self.repo)
        git(self.repo, "checkout", "--detach", "-q", "HEAD")
        detached = identity.discover_git_identity(self.repo)

        self.assertEqual(before.repo_id, on_branch.repo_id)
        self.assertEqual(before.worktree_id, on_branch.worktree_id)
        self.assertEqual(before.worktree_id, detached.worktree_id)
        self.assertEqual(on_branch.branch, "feature")
        self.assertTrue(detached.detached)
        self.assertIsNone(detached.branch)

    def test_unborn_repository_has_stable_identity_without_head(self) -> None:
        identity = import_api("agent_project_memory.identity")
        unborn = self.root / "unborn"
        unborn.mkdir()
        git(unborn, "init", "-q")

        result = identity.discover_git_identity(unborn)

        self.assertIsNone(result.head)
        self.assertTrue(result.unborn)
        self.assertTrue(result.repo_id)
        self.assertTrue(result.worktree_id)

    def test_non_git_directory_returns_none(self) -> None:
        identity = import_api("agent_project_memory.identity")
        plain = self.root / "plain"
        plain.mkdir()

        self.assertIsNone(identity.discover_git_identity(plain))


if __name__ == "__main__":
    unittest.main(verbosity=2)
