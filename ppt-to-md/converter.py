"""CLI shim: `python converter.py input.pptx output.md` from ppt-to-md directory."""

from __future__ import annotations

from src.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
