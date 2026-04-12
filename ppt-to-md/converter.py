"""Shim CLI: prefer `md-ppt` after `pip install mdengine`."""

from __future__ import annotations

from md_generator.ppt.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
