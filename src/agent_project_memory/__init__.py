"""Safe, standard-library continuity primitives for agent project memory."""

from .config import Config, ConfigLoadResult, load_config
from .io import (
    PROCESS_LOCKING_AVAILABLE,
    AtomicWriteError,
    JsonReadResult,
    JsonlAppendError,
    append_jsonl,
    atomic_write_bytes,
    atomic_write_text,
    ensure_private_directory,
    read_json_state,
    write_json_state,
)
from .privacy import (
    PathClassification,
    PromptSummary,
    SensitiveScan,
    classify_sensitive_path,
    is_digest_only,
    scan_sensitive_text,
    summarize_prompt,
)

__all__ = [
    "Config",
    "ConfigLoadResult",
    "PROCESS_LOCKING_AVAILABLE",
    "AtomicWriteError",
    "JsonReadResult",
    "JsonlAppendError",
    "PathClassification",
    "PromptSummary",
    "SensitiveScan",
    "append_jsonl",
    "atomic_write_bytes",
    "atomic_write_text",
    "classify_sensitive_path",
    "ensure_private_directory",
    "is_digest_only",
    "load_config",
    "read_json_state",
    "scan_sensitive_text",
    "summarize_prompt",
    "write_json_state",
]
__version__ = "2.0.0.dev0"
