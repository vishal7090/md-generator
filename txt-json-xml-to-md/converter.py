"""Shim CLI: prefer `md-text` after `pip install md-generator`."""

from __future__ import annotations

from md_generator.text.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
