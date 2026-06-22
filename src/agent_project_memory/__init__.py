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
    changed_worktree_paths,
    checkpoint_refs,
    create_git_checkpoint,
    legacy_checkpoint_refs,
)
from .continuity import (
    ContinuityResult,
    continuity_state_dir,
    handle_hook_event,
    mark_recovered,
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
from .recovery import (
    TranscriptTailIndex,
    index_transcript_tail,
    write_recovery_artifacts,
)

__all__ = [
    "Config",
    "ConfigLoadResult",
    "CheckpointResult",
    "ContinuityResult",
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
    "TranscriptTailIndex",
    "append_jsonl",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "classify_sensitive_path",
    "classify_root",
    "changed_worktree_paths",
    "checkpoint_refs",
    "create_git_checkpoint",
    "continuity_state_dir",
    "discover_git_identity",
    "ensure_private_directory",
    "handle_hook_event",
    "index_transcript_tail",
    "is_digest_only",
    "load_config",
    "legacy_checkpoint_refs",
    "mark_recovered",
    "parse_toml_subset",
    "process_lock",
    "process_lock_backend",
    "read_json_state",
    "scan_sensitive_text",
    "summarize_prompt",
    "write_json_state",
    "write_recovery_artifacts",
]
__version__ = "2.0.0.dev0"
