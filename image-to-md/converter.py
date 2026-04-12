"""Shim CLI: prefer `md-image` after `pip install mdengine`."""

from __future__ import annotations

from md_generator.image.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
