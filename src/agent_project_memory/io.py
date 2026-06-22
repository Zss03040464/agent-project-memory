"""Private, atomic state I/O for continuity components."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised on Windows runners
    _fcntl = None  # type: ignore

try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX runners
    _msvcrt = None  # type: ignore


PROCESS_LOCKING_AVAILABLE = _fcntl is not None or _msvcrt is not None


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
    missing = []
    candidate = directory
    while not candidate.exists():
        missing.append(candidate)
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    for component in reversed(missing):
        component.mkdir(exist_ok=True, mode=0o700)
        os.chmod(str(component), 0o700)
    os.chmod(str(directory), 0o700)
    return directory


def process_lock_backend() -> Optional[str]:
    if _fcntl is not None:
        return "fcntl"
    if _msvcrt is not None:
        return "msvcrt"
    return None


@contextmanager
def process_lock(path: Path) -> Iterator[None]:
    """Hold a standard-library inter-process lock for the given lock file."""

    lock_path = Path(path)
    ensure_private_directory(lock_path.parent)
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    backend = process_lock_backend()
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        if backend == "fcntl":
            _fcntl.flock(descriptor, _fcntl.LOCK_EX)
        elif backend == "msvcrt":
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            _msvcrt.locking(descriptor, _msvcrt.LK_LOCK, 1)
        else:
            raise JsonlAppendError("process locking unavailable")
        yield
    finally:
        try:
            if backend == "fcntl":
                _fcntl.flock(descriptor, _fcntl.LOCK_UN)
            elif backend == "msvcrt":
                os.lseek(descriptor, 0, os.SEEK_SET)
                _msvcrt.locking(descriptor, _msvcrt.LK_UNLCK, 1)
        finally:
            os.close(descriptor)


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


def append_jsonl(
    path: Path,
    record: Mapping[str, Any],
    *,
    schema_version: int = 1,
) -> None:
    """Append one schema-stamped JSON record under an inter-process lock."""

    if type(schema_version) is not int or schema_version <= 0:
        raise ValueError("schema_version must be a positive integer")
    try:
        document = dict(record)
        document["schema_version"] = schema_version
        line = (
            json.dumps(
                document,
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
        with process_lock(target.with_name(target.name + ".lock")):
            _append_line(target, line)
    except Exception as exc:
        if isinstance(exc, JsonlAppendError):
            raise
        raise JsonlAppendError("jsonl append failed") from None

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
