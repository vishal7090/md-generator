"""Shim CLI: prefer `md-xlsx` after `pip install mdengine`."""

from __future__ import annotations

from md_generator.xlsx.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
