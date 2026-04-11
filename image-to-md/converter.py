"""CLI shim: `python converter.py input out.md` from image-to-md directory."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
