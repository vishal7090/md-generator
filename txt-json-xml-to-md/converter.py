"""CLI shim: `python converter.py input.json output.md` from txt-json-xml-to-md directory."""

from __future__ import annotations

from src.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
