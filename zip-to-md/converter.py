"""Shim CLI: prefer `md-zip` after `pip install mdengine`."""

from __future__ import annotations

from md_generator.archive.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
