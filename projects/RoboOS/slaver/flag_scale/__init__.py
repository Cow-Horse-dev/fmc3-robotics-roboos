from __future__ import annotations

import importlib
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_FLAG_SCALE_SRC = _ROOT / "FlagScale"

if _FLAG_SCALE_SRC.exists():
    flag_scale_path = str(_FLAG_SCALE_SRC)
    if flag_scale_path not in sys.path:
        sys.path.insert(0, flag_scale_path)

    try:
        _flagscale = importlib.import_module("flagscale")
    except Exception as exc:  # pragma: no cover - import failure surfaces to caller
        raise ImportError(
            f"Failed to import 'flagscale' from {_FLAG_SCALE_SRC}"
        ) from exc

    sys.modules.setdefault("flag_scale.flagscale", _flagscale)
    setattr(sys.modules[__name__], "flagscale", _flagscale)
else:  # pragma: no cover - only triggers when repo layout is broken
    raise ImportError(f"FlagScale source not found at {_FLAG_SCALE_SRC}")
