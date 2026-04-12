"""Shim CLI: prefer `md-word` after `pip install mdengine`."""

from __future__ import annotations

from md_generator.word.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
