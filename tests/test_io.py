from __future__ import annotations

import json
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import import_api


class _ExplodingMapping:
    def keys(self):
        raise OSError("DO_NOT_ECHO_MAPPING_ERROR")


class _FakeMsvcrt:
    LK_LOCK = 1
    LK_UNLCK = 2

    def __init__(self) -> None:
        self.calls = []
        self.held = False

    def locking(self, descriptor, mode, count) -> None:
        self.calls.append((descriptor, mode, count))
        if mode == self.LK_LOCK:
            self.held = True
        elif mode == self.LK_UNLCK:
            self.held = False


class _AcquireFailingMsvcrt(_FakeMsvcrt):
    def __init__(self) -> None:
        super().__init__()
        self.unlock_attempted = False

    def locking(self, descriptor, mode, count) -> None:
        self.calls.append((descriptor, mode, count))
        if mode == self.LK_LOCK:
            raise OSError("PRIVATE ACQUIRE DETAIL")
        self.unlock_attempted = True
        raise AssertionError("unlock must not run after acquire failure")


def _append_worker(path_text: str, worker: int, count: int) -> None:
    io_mod = import_api("agent_project_memory.io")
    path = Path(path_text)
    for sequence in range(count):
        io_mod.append_jsonl(path, {"worker": worker, "sequence": sequence})


class AtomicIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="apm-io-")
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_private_directory_and_file_permissions(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "private" / "state.json"

        io_mod.atomic_write_text(target, "safe")

        self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_all_newly_created_directory_ancestors_are_private(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        private_root = self.root / "state"
        target = private_root / "sessions" / "current" / "state.json"

        io_mod.atomic_write_text(target, "safe")

        for directory in (
            private_root,
            private_root / "sessions",
            private_root / "sessions" / "current",
        ):
            with self.subTest(directory=directory.name):
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_existing_parent_mode_is_preserved_while_new_children_are_private(
        self,
    ) -> None:
        io_mod = import_api("agent_project_memory.io")
        project_root = self.root / "existing-project"
        project_root.mkdir(mode=0o755)
        os.chmod(project_root, 0o755)
        target = project_root / "state" / "sessions"

        io_mod.ensure_private_directory(target)

        self.assertEqual(stat.S_IMODE(project_root.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((project_root / "state").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)

    def test_atomic_write_does_not_chmod_existing_project_root(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        project_root = self.root / "existing-project"
        project_root.mkdir(mode=0o755)
        os.chmod(project_root, 0o755)

        io_mod.atomic_write_text(project_root / "state.json", "safe")

        self.assertEqual(stat.S_IMODE(project_root.stat().st_mode), 0o755)

    def test_atomic_write_replaces_and_fsyncs_file_and_parent(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.txt"
        target.write_text("old", encoding="utf-8")
        previous_inode = target.stat().st_ino

        io_mod.atomic_write_text(target, "new")

        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        self.assertNotEqual(target.stat().st_ino, previous_inode)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertFalse(any(target.parent.glob(f".{target.name}.*.tmp")))

    def test_committed_replace_is_not_reported_failed_by_post_replace_chmod(
        self,
    ) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.txt"
        target.write_text("old", encoding="utf-8")

        with mock.patch.object(
            io_mod.os,
            "chmod",
            side_effect=OSError("post-replace permission failure"),
        ):
            try:
                io_mod.atomic_write_text(target, "new")
            except io_mod.AtomicWriteError:
                self.fail("a committed replace must not be reported as failed")

        self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_committed_replace_is_not_reported_failed_by_directory_sync(
        self,
    ) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.txt"

        with mock.patch.object(
            io_mod,
            "_fsync_directory",
            side_effect=OSError("post-replace directory sync failure"),
        ):
            try:
                io_mod.atomic_write_text(target, "committed")
            except io_mod.AtomicWriteError:
                self.fail("post-commit durability failure must be best effort")

        self.assertEqual(target.read_text(encoding="utf-8"), "committed")

    def test_json_state_round_trip_always_contains_schema_version(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.json"

        io_mod.write_json_state(target, {"phase": "ready"}, schema_version=2)
        result = io_mod.read_json_state(
            target, schema_version=2, default={"phase": "idle"}
        )

        self.assertFalse(result.recovered)
        self.assertEqual(result.diagnostic, None)
        self.assertEqual(result.data, {"schema_version": 2, "phase": "ready"})
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["schema_version"], 2)

    def test_recovered_json_state_deep_copies_nested_defaults(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        default = {"nested": {"items": ["original"]}}

        result = io_mod.read_json_state(
            self.root / "missing.json",
            schema_version=1,
            default=default,
        )
        result.data["nested"]["items"].append("changed")

        self.assertEqual(default, {"nested": {"items": ["original"]}})

    def test_damaged_or_wrong_schema_state_recovers_without_echoing_content(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.json"
        marker = "DO_NOT_ECHO_STATE_CONTENT"

        for damaged in (
            f'{{"schema_version": 2, "secret": "{marker}"',
            f'{{"schema_version": 99, "secret": "{marker}"}}',
            f'{{"secret": "{marker}"}}',
        ):
            with self.subTest(damaged=damaged[:20]):
                target.write_text(damaged, encoding="utf-8")
                result = io_mod.read_json_state(
                    target, schema_version=2, default={"phase": "idle"}
                )
                self.assertTrue(result.recovered)
                self.assertEqual(
                    result.data, {"schema_version": 2, "phase": "idle"}
                )
                self.assertNotIn(marker, result.diagnostic or "")
                self.assertNotIn(marker, repr(result))

    def test_concurrent_jsonl_append_produces_complete_valid_records(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "events.jsonl"
        workers = 4
        per_worker = 30
        context = multiprocessing.get_context("spawn")
        processes = [
            context.Process(
                target=_append_worker, args=(str(target), worker, per_worker)
            )
            for worker in range(workers)
        ]

        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertEqual(process.exitcode, 0)

        records = [
            json.loads(line)
            for line in target.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records), workers * per_worker)
        self.assertEqual(
            {(record["worker"], record["sequence"]) for record in records},
            {
                (worker, sequence)
                for worker in range(workers)
                for sequence in range(per_worker)
            },
        )
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertIn(io_mod.process_lock_backend(), {"fcntl", "msvcrt"})

    def test_jsonl_append_injects_schema_without_mutating_caller_record(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "events.jsonl"
        record = {"event": "checkpoint"}

        io_mod.append_jsonl(target, record)

        self.assertEqual(record, {"event": "checkpoint"})
        stored = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(
            stored, {"schema_version": 1, "event": "checkpoint"}
        )

    def test_process_lock_selects_msvcrt_when_fcntl_is_unavailable(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        self.assertTrue(
            hasattr(io_mod, "process_lock"),
            "a unified process_lock API is required",
        )
        fake_msvcrt = _FakeMsvcrt()
        lock_path = self.root / "events.lock"

        with mock.patch.object(io_mod, "_fcntl", None):
            with mock.patch.object(io_mod, "_msvcrt", fake_msvcrt):
                self.assertEqual(io_mod.process_lock_backend(), "msvcrt")
                with io_mod.process_lock(lock_path):
                    self.assertTrue(lock_path.is_file())
                    self.assertTrue(fake_msvcrt.held)

        self.assertFalse(fake_msvcrt.held)

    def test_failed_lock_acquire_is_not_unlocked_or_leaked_by_process_api(
        self,
    ) -> None:
        io_mod = import_api("agent_project_memory.io")
        fake_msvcrt = _AcquireFailingMsvcrt()
        self.assertTrue(
            hasattr(io_mod, "ProcessLockError"),
            "process lock failures need a dedicated public error",
        )

        with mock.patch.object(io_mod, "_fcntl", None):
            with mock.patch.object(io_mod, "_msvcrt", fake_msvcrt):
                with self.assertRaises(io_mod.ProcessLockError) as raised:
                    with io_mod.process_lock(self.root / "state.lock"):
                        self.fail("lock body must not run")

        self.assertEqual(str(raised.exception), "process lock acquire failed")
        self.assertFalse(fake_msvcrt.unlock_attempted)

    def test_jsonl_converts_process_lock_failure_to_jsonl_error(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        fake_msvcrt = _AcquireFailingMsvcrt()

        with mock.patch.object(io_mod, "_fcntl", None):
            with mock.patch.object(io_mod, "_msvcrt", fake_msvcrt):
                with self.assertRaises(io_mod.JsonlAppendError) as raised:
                    io_mod.append_jsonl(
                        self.root / "events.jsonl", {"event": "checkpoint"}
                    )

        self.assertEqual(str(raised.exception), "jsonl append failed")
        self.assertNotIn("PRIVATE", repr(raised.exception))

    def test_windows_without_fchmod_writes_json_and_jsonl_end_to_end(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        self.assertTrue(
            hasattr(io_mod, "atomic_write_json"),
            "atomic_write_json API is required",
        )
        fake_msvcrt = _FakeMsvcrt()
        state_path = self.root / "windows" / "state.json"
        events_path = self.root / "windows" / "events.jsonl"

        with mock.patch.object(io_mod, "_fcntl", None):
            with mock.patch.object(io_mod, "_msvcrt", fake_msvcrt):
                with mock.patch.object(io_mod.os, "fchmod", None):
                    io_mod.atomic_write_json(
                        state_path,
                        {"phase": "ready"},
                        schema_version=2,
                    )
                    io_mod.append_jsonl(
                        events_path,
                        {"event": "checkpoint"},
                        schema_version=2,
                    )

        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8")),
            {"schema_version": 2, "phase": "ready"},
        )
        self.assertEqual(
            json.loads(events_path.read_text(encoding="utf-8")),
            {"schema_version": 2, "event": "checkpoint"},
        )
        self.assertEqual(stat.S_IMODE(state_path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(state_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(events_path.stat().st_mode), 0o600)
        self.assertFalse(fake_msvcrt.held)

    def test_write_failure_does_not_echo_payload(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.txt"
        marker = "DO_NOT_ECHO_WRITE_PAYLOAD"

        with mock.patch.object(os, "replace", side_effect=OSError("internal detail")):
            with self.assertRaises(io_mod.AtomicWriteError) as raised:
                io_mod.atomic_write_text(target, marker)

        rendered = str(raised.exception)
        self.assertNotIn(marker, rendered)
        self.assertNotIn("internal detail", rendered)
        self.assertEqual(rendered, "atomic write failed")

    def test_text_encoding_failure_does_not_echo_payload(self) -> None:
        io_mod = import_api("agent_project_memory.io")
        target = self.root / "state.txt"
        unencodable = "private" + "\udcff"

        try:
            io_mod.atomic_write_text(target, unencodable)
        except io_mod.AtomicWriteError as exc:
            raised = exc
        except Exception as exc:
            self.fail(
                "expected privacy-safe AtomicWriteError, got "
                + type(exc).__name__
            )
        else:
            self.fail("expected text encoding to fail")

        self.assertEqual(str(raised), "text encoding failed")
        self.assertNotIn("private", repr(raised))

    def test_json_mapping_failure_does_not_echo_internal_error(self) -> None:
        io_mod = import_api("agent_project_memory.io")

        try:
            io_mod.write_json_state(
                self.root / "state.json",
                _ExplodingMapping(),
                schema_version=1,
            )
        except io_mod.AtomicWriteError as exc:
            raised = exc
        except Exception as exc:
            self.fail(
                "expected privacy-safe AtomicWriteError, got "
                + type(exc).__name__
            )
        else:
            self.fail("expected mapping conversion to fail")

        self.assertEqual(str(raised), "json serialization failed")
        self.assertNotIn("DO_NOT_ECHO", repr(raised))


if __name__ == "__main__":
    unittest.main(verbosity=2)
