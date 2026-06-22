"""Private, atomic state I/O for continuity components."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows runners
    fcntl = None  # type: ignore


PROCESS_LOCKING_AVAILABLE = fcntl is not None
_FALLBACK_APPEND_LOCK = threading.Lock()


class AtomicWriteError(RuntimeError):
    """An atomic write failed without exposing its payload."""


class JsonlAppendError(RuntimeError):
    """A JSONL append failed without exposing its record."""


@dataclass(frozen=True)
class JsonReadResult:
    data: Dict[str, Any]
    recovered: bool
    diagnostic: Optional[str] = None


def ensure_private_directory(path: Path) -> Path:
    """Create a directory and constrain its mode to owner-only access."""

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(str(directory), 0o700)
    return directory


def atomic_write_text(path: Path, text: str) -> None:
    try:
        payload = text.encode("utf-8")
    except UnicodeError:
        raise AtomicWriteError("text encoding failed") from None
    atomic_write_bytes(path, payload)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write bytes via a private temporary file, fsync, and atomic replace."""

    target = Path(path)
    temporary: Optional[Path] = None
    descriptor: Optional[int] = None
    try:
        ensure_private_directory(target.parent)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{}.".format(target.name),
            suffix=".tmp",
            dir=str(target.parent),
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(target))
        temporary = None
        os.chmod(str(target), 0o600)
        _fsync_directory(target.parent)
    except Exception:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        raise AtomicWriteError("atomic write failed") from None


def write_json_state(
    path: Path, state: Mapping[str, Any], *, schema_version: int
) -> None:
    """Atomically persist a JSON object with a mandatory schema version."""

    if type(schema_version) is not int or schema_version <= 0:
        raise ValueError("schema_version must be a positive integer")
    try:
        document = dict(state)
        document["schema_version"] = schema_version
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        raise AtomicWriteError("json serialization failed") from None
    atomic_write_bytes(path, payload)


def read_json_state(
    path: Path,
    *,
    schema_version: int,
    default: Mapping[str, Any],
) -> JsonReadResult:
    """Read state or recover to a schema-stamped default without raising."""

    fallback = dict(default)
    fallback["schema_version"] = schema_version
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return JsonReadResult(fallback, True, "state missing; using default")
    except (OSError, UnicodeError):
        return JsonReadResult(fallback, True, "state unreadable; using default")
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("state is not an object")
        if data.get("schema_version") != schema_version:
            raise ValueError("schema mismatch")
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonReadResult(fallback, True, "state invalid; using default")
    return JsonReadResult(data, False)


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Append one compact JSON record under a process lock where available."""

    try:
        line = (
            json.dumps(
                dict(record),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
    except Exception:
        raise JsonlAppendError("jsonl serialization failed") from None

    target = Path(path)
    try:
        ensure_private_directory(target.parent)
        if fcntl is None:
            with _FALLBACK_APPEND_LOCK:
                _append_line(target, line)
        else:
            _append_line_with_process_lock(target, line)
    except Exception as exc:
        if isinstance(exc, JsonlAppendError):
            raise
        raise JsonlAppendError("jsonl append failed") from None


def _append_line_with_process_lock(target: Path, line: bytes) -> None:
    lock_path = target.with_name(target.name + ".lock")
    lock_descriptor = os.open(
        str(lock_path), os.O_CREAT | os.O_RDWR, 0o600
    )
    try:
        os.fchmod(lock_descriptor, 0o600)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        _append_line(target, line)
    finally:
        try:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        finally:
            os.close(lock_descriptor)


def _append_line(target: Path, line: bytes) -> None:
    descriptor = os.open(
        str(target), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600
    )
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(line)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short append")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(target.parent)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(directory), flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)
