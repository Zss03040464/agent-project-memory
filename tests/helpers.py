from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def import_api(module_name: str):
    src = str(SRC)
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise AssertionError(
            f"expected importable API module {module_name!r}, got {type(exc).__name__}"
        ) from None
