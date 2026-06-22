"""Safe, standard-library continuity primitives for agent project memory."""

from .config import (
    Config,
    ConfigLoadResult,
    RootClassification,
    classify_root,
    load_config,
    parse_toml_subset,
)
from .checkpoint import (
    CheckpointResult,
    checkpoint_refs,
    create_git_checkpoint,
    legacy_checkpoint_refs,
)
from .identity import GitIdentity, discover_git_identity
from .io import (
    PROCESS_LOCKING_AVAILABLE,
    AtomicWriteError,
    JsonReadResult,
    JsonlAppendError,
    ProcessLockError,
    append_jsonl,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    ensure_private_directory,
    process_lock,
    process_lock_backend,
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
    "CheckpointResult",
    "GitIdentity",
    "RootClassification",
    "PROCESS_LOCKING_AVAILABLE",
    "AtomicWriteError",
    "JsonReadResult",
    "JsonlAppendError",
    "ProcessLockError",
    "PathClassification",
    "PromptSummary",
    "SensitiveScan",
    "append_jsonl",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "classify_sensitive_path",
    "classify_root",
    "checkpoint_refs",
    "create_git_checkpoint",
    "discover_git_identity",
    "ensure_private_directory",
    "is_digest_only",
    "load_config",
    "legacy_checkpoint_refs",
    "parse_toml_subset",
    "process_lock",
    "process_lock_backend",
    "read_json_state",
    "scan_sensitive_text",
    "summarize_prompt",
    "write_json_state",
]
__version__ = "2.0.0.dev0"
