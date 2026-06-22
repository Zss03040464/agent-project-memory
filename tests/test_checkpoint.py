from __future__ import annotations

import json
import multiprocessing
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import import_api


def git(
    cwd: Path,
    *args: str,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", "replace"))
    return result.stdout


def git_text(cwd: Path, *args: str, check: bool = True) -> str:
    return git(cwd, *args, check=check).decode("utf-8", "replace").strip()


def initialize_repo(path: Path) -> None:
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test User")
    git(path, "config", "user.email", "test@invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-qm", "base")


def repository_snapshot(path: Path) -> dict[str, str]:
    return {
        "status": git(path, "status", "--porcelain=v2", "-z").decode(
            "utf-8", "surrogateescape"
        ),
        "head": git_text(path, "rev-parse", "HEAD"),
        "branch": git_text(path, "branch", "--show-current"),
        "index": git_text(path, "write-tree"),
    }


def checkpoint_worker(path_text: str) -> None:
    checkpoint = import_api("agent_project_memory.checkpoint")
    checkpoint.create_git_checkpoint(Path(path_text), event="PostToolUse")


class GitCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-checkpoint-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        initialize_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_two_worktrees_get_independent_refs_locks_and_debounce(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        identity = import_api("agent_project_memory.identity")
        second = self.root / "second"
        git(self.repo, "worktree", "add", "--detach", str(second), "HEAD")
        (self.repo / "tracked.txt").write_text("primary\n", encoding="utf-8")
        (second / "tracked.txt").write_text("second\n", encoding="utf-8")

        primary = checkpoint.create_git_checkpoint(
            self.repo, event="PostToolUse", debounce_seconds=20
        )
        other = checkpoint.create_git_checkpoint(
            second, event="PostToolUse", debounce_seconds=20
        )
        primary_identity = identity.discover_git_identity(self.repo)
        other_identity = identity.discover_git_identity(second)

        self.assertTrue(primary.created)
        self.assertTrue(other.created)
        self.assertNotEqual(primary.latest_ref, other.latest_ref)
        self.assertIn(primary_identity.worktree_id, primary.latest_ref)
        self.assertIn(other_identity.worktree_id, other.latest_ref)
        self.assertEqual(git_text(self.repo, "rev-parse", primary.latest_ref), primary.commit)
        self.assertEqual(git_text(second, "rev-parse", other.latest_ref), other.commit)
        self.assertNotEqual(primary.state_dir, other.state_dir)
        for result in (primary, other):
            self.assertTrue((result.state_dir / "checkpoint.lock").exists())
            self.assertEqual(
                stat.S_IMODE((result.state_dir / "checkpoint.lock").stat().st_mode),
                0o600,
            )

    def test_checkpoint_never_changes_head_branch_index_or_worktree(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new file 中文.txt").write_text("new\n", encoding="utf-8")
        git(self.repo, "add", "tracked.txt")
        (self.repo / "tracked.txt").write_text("changed after stage\n", encoding="utf-8")
        before = repository_snapshot(self.repo)

        result = checkpoint.create_git_checkpoint(self.repo, event="Stop")

        after = repository_snapshot(self.repo)
        self.assertTrue(result.created)
        self.assertEqual(before, after)
        tree_paths = set(
            git(
                self.repo,
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                result.commit,
            ).split(b"\0")
        )
        self.assertIn("new file 中文.txt".encode(), tree_paths)
        self.assertEqual(
            git(self.repo, "show", f"{result.commit}:tracked.txt"),
            b"changed after stage\n",
        )

    def test_sensitive_ignored_generated_and_nested_repo_paths_are_excluded(
        self,
    ) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-qm", "ignore")
        (self.repo / "safe.txt").write_text("safe\n", encoding="utf-8")
        (self.repo / ".env").write_text("PASSWORD=private-value\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        (self.repo / "node_modules").mkdir()
        (self.repo / "node_modules/pkg.js").write_text("generated\n", encoding="utf-8")
        nested = self.repo / "nested"
        nested.mkdir()
        git(nested, "init", "-q")
        (nested / "inside.txt").write_text("nested\n", encoding="utf-8")

        result = checkpoint.create_git_checkpoint(self.repo, event="Stop")
        paths = {
            item.decode("utf-8", "surrogateescape")
            for item in git(
                self.repo, "ls-tree", "-r", "-z", "--name-only", result.commit
            ).split(b"\0")
            if item
        }

        self.assertIn("safe.txt", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("ignored.txt", paths)
        self.assertNotIn("node_modules/pkg.js", paths)
        self.assertNotIn("nested/inside.txt", paths)

    def test_tracked_sensitive_change_keeps_head_version(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        tracked_secret = self.repo / "auth.json"
        tracked_secret.write_text('{"value":"placeholder"}\n', encoding="utf-8")
        git(self.repo, "add", "auth.json")
        git(self.repo, "commit", "-qm", "tracked placeholder")
        tracked_secret.write_text(
            '{"value":"DO_NOT_CHECKPOINT"}\n', encoding="utf-8"
        )
        (self.repo / "safe.txt").write_text("safe\n", encoding="utf-8")

        result = checkpoint.create_git_checkpoint(self.repo, event="Stop")

        self.assertEqual(
            git(self.repo, "show", f"{result.commit}:auth.json"),
            b'{"value":"placeholder"}\n',
        )
        self.assertEqual(
            git(self.repo, "show", f"{result.commit}:safe.txt"), b"safe\n"
        )

    def test_symlink_is_saved_without_reading_external_target(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        external = self.root / "external-private.txt"
        external.write_text(
            "-----BEGIN " + "PRIVATE KEY-----\nPRIVATE\n", encoding="utf-8"
        )
        link = self.repo / "external-link"
        link.symlink_to(external)

        result = checkpoint.create_git_checkpoint(self.repo, event="Stop")

        self.assertEqual(
            git_text(
                self.repo,
                "ls-tree",
                result.commit,
                "external-link",
            ).split()[0],
            "120000",
        )
        self.assertEqual(
            git(self.repo, "show", f"{result.commit}:external-link"),
            os.fsencode(str(external)),
        )

    def test_file_and_total_size_limits_skip_without_touching_worktree(
        self,
    ) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        (self.repo / "small.txt").write_bytes(b"a" * 8)
        (self.repo / "large.bin").write_bytes(b"b" * 64)
        before = repository_snapshot(self.repo)

        result = checkpoint.create_git_checkpoint(
            self.repo,
            event="Stop",
            max_file_bytes=16,
            max_total_bytes=128,
        )
        after = repository_snapshot(self.repo)
        paths = set(
            git_text(
                self.repo, "ls-tree", "-r", "--name-only", result.commit
            ).splitlines()
        )

        self.assertEqual(before, after)
        self.assertIn("small.txt", paths)
        self.assertNotIn("large.bin", paths)
        (self.repo / "another.txt").write_bytes(b"c" * 12)
        cancelled = checkpoint.create_git_checkpoint(
            self.repo,
            event="Stop",
            max_file_bytes=16,
            max_total_bytes=16,
        )
        self.assertFalse(cancelled.created)
        self.assertEqual(cancelled.reason, "no-allowed-changes")
        self.assertIn("total-size-limit", cancelled.skipped_categories)

    def test_lfs_marked_path_uses_git_clean_filter_and_bypasses_raw_size_limit(
        self,
    ) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        filter_script = self.root / "lfs-clean.sh"
        filter_script.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "printf 'version https://git-lfs.github.com/spec/v1\\n"
            "oid sha256:placeholder\\nsize 128\\n'\n",
            encoding="utf-8",
        )
        filter_script.chmod(0o755)
        git(self.repo, "config", "filter.lfs.clean", str(filter_script))
        git(self.repo, "config", "filter.lfs.smudge", "cat")
        git(self.repo, "config", "filter.lfs.required", "false")
        (self.repo / ".gitattributes").write_text(
            "asset.bin filter=lfs\n", encoding="utf-8"
        )
        (self.repo / "asset.bin").write_bytes(b"x" * 128)

        result = checkpoint.create_git_checkpoint(
            self.repo,
            event="Stop",
            max_file_bytes=16,
        )

        stored = git(self.repo, "show", f"{result.commit}:asset.bin")
        self.assertIn(b"git-lfs.github.com/spec/v1", stored)
        self.assertNotEqual(stored, b"x" * 128)

    def test_unborn_detached_and_branch_switch_create_valid_checkpoints(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        identity = import_api("agent_project_memory.identity")
        unborn = self.root / "unborn"
        unborn.mkdir()
        git(unborn, "init", "-q")
        (unborn / "first.txt").write_text("first\n", encoding="utf-8")
        unborn_result = checkpoint.create_git_checkpoint(unborn, event="Stop")
        self.assertTrue(unborn_result.created)
        self.assertEqual(
            git_text(unborn, "rev-list", "--parents", "-n", "1", unborn_result.commit),
            unborn_result.commit,
        )

        before_id = identity.discover_git_identity(self.repo).worktree_id
        git(self.repo, "checkout", "--detach", "-q", "HEAD")
        (self.repo / "tracked.txt").write_text("detached\n", encoding="utf-8")
        detached_result = checkpoint.create_git_checkpoint(self.repo, event="Stop")
        git(self.repo, "switch", "-qc", "new-branch")
        (self.repo / "tracked.txt").write_text("branch\n", encoding="utf-8")
        branch_result = checkpoint.create_git_checkpoint(self.repo, event="Stop")

        self.assertEqual(before_id, identity.discover_git_identity(self.repo).worktree_id)
        self.assertEqual(detached_result.latest_ref, branch_result.latest_ref)
        self.assertTrue(detached_result.created)
        self.assertTrue(branch_result.created)

    def test_debounce_duplicate_tree_concurrency_and_retention_are_scoped(
        self,
    ) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        (self.repo / "tracked.txt").write_text("one\n", encoding="utf-8")
        first = checkpoint.create_git_checkpoint(
            self.repo, event="PostToolUse", debounce_seconds=30, retention=2
        )
        debounced = checkpoint.create_git_checkpoint(
            self.repo, event="PostToolUse", debounce_seconds=30, retention=2
        )
        forced_duplicate = checkpoint.create_git_checkpoint(
            self.repo, event="Stop", debounce_seconds=30, retention=2
        )

        self.assertTrue(first.created)
        self.assertEqual(debounced.reason, "debounced")
        self.assertEqual(forced_duplicate.reason, "duplicate-tree")

        context = multiprocessing.get_context("spawn")
        (self.repo / "tracked.txt").write_text("two\n", encoding="utf-8")
        processes = [
            context.Process(target=checkpoint_worker, args=(str(self.repo),))
            for _ in range(3)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertEqual(process.exitcode, 0)

        for value in ("three", "four"):
            (self.repo / "tracked.txt").write_text(value + "\n", encoding="utf-8")
            checkpoint.create_git_checkpoint(
                self.repo, event="Stop", retention=2
            )
        history = git_text(
            self.repo,
            "for-each-ref",
            "--format=%(refname)",
            first.history_prefix,
        ).splitlines()
        self.assertEqual(len(history), 2)

    def test_legacy_refs_are_read_only_and_reported_as_migration_hints(self) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        legacy = "refs/codex/checkpoints/latest"
        head = git_text(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-ref", legacy, head)
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")

        result = checkpoint.create_git_checkpoint(self.repo, event="Stop")
        hints = checkpoint.legacy_checkpoint_refs(self.repo)

        self.assertEqual(git_text(self.repo, "rev-parse", legacy), head)
        self.assertIn(legacy, hints)
        self.assertNotEqual(result.latest_ref, legacy)

    def test_removed_worktree_leaves_inspectable_ref_without_breaking_repo(
        self,
    ) -> None:
        checkpoint = import_api("agent_project_memory.checkpoint")
        second = self.root / "second"
        git(self.repo, "worktree", "add", "--detach", str(second), "HEAD")
        (second / "tracked.txt").write_text("second\n", encoding="utf-8")
        result = checkpoint.create_git_checkpoint(second, event="Stop")

        git(self.repo, "worktree", "remove", "--force", str(second))

        self.assertEqual(
            git_text(self.repo, "rev-parse", result.latest_ref), result.commit
        )
        self.assertEqual(git_text(self.repo, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
