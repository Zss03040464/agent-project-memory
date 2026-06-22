"""Evidence-counted feedback ledger, promotion, and rollback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .io import append_jsonl, atomic_write_text, ensure_private_directory


@dataclass(frozen=True)
class PromotionDecision:
    rule_id: str
    promoted: bool
    distinct_evidence_count: int
    blocked_by_conflict: bool = False


def record_feedback(
    root: Path,
    *,
    category: str,
    scope: str,
    session_id: str,
    turn_id: str,
    normalized_intent: str,
    evidence_pointer: str,
    conflict: bool = False,
    threshold: int = 2,
) -> PromotionDecision:
    base = ensure_private_directory(Path(root))
    rule_id = hashlib.sha256(
        (category + "\0" + scope + "\0" + normalized_intent).encode("utf-8")
    ).hexdigest()[:20]
    event = {
        "rule_id": rule_id,
        "category": category,
        "scope": scope,
        "session_id": session_id,
        "turn_id": turn_id,
        "normalized_intent": normalized_intent,
        "evidence_pointer": evidence_pointer,
        "conflict": conflict,
    }
    append_jsonl(base / "events.jsonl", event)
    events = _events(base / "events.jsonl")
    related = [
        item
        for item in events
        if item.get("category") == category and item.get("scope") == scope
    ]
    blocked = any(bool(item.get("conflict")) for item in related)
    evidence = {
        (str(item.get("session_id")), str(item.get("turn_id")))
        for item in related
        if item.get("normalized_intent") == normalized_intent
        and not item.get("conflict")
    }
    promoted = len(evidence) >= max(2, threshold) and not blocked
    if promoted:
        _write_promotion(base, rule_id, category, scope, normalized_intent, len(evidence))
    return PromotionDecision(rule_id, promoted, len(evidence), blocked)


def rollback_promotion(root: Path, rule_id: str, *, reason: str) -> None:
    base = ensure_private_directory(Path(root))
    append_jsonl(
        base / "events.jsonl",
        {"event": "rollback", "rule_id": rule_id, "reason": reason},
    )
    learned = base / "learned-rules.md"
    existing = learned.read_text(encoding="utf-8") if learned.exists() else "# Learned Rules\n"
    atomic_write_text(
        learned,
        existing.rstrip()
        + "\n\n- `{}` rolled back; reason recorded in private event ledger.\n".format(
            rule_id
        ),
    )


def _events(path: Path) -> List[Dict[str, object]]:
    result = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for line in lines:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
        except json.JSONDecodeError:
            continue
    return result


def _write_promotion(
    root: Path,
    rule_id: str,
    category: str,
    scope: str,
    intent: str,
    count: int,
) -> None:
    learned = root / "learned-rules.md"
    text = learned.read_text(encoding="utf-8") if learned.exists() else "# Learned Rules\n"
    marker = "- `{}`".format(rule_id)
    if marker in text:
        return
    atomic_write_text(
        learned,
        text.rstrip()
        + "\n\n{} [{} / {} evidence] {}\n".format(
            marker, scope, count, intent
        ),
    )
