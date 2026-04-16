"""Shim CLI: prefer `md-url` after `pip install mdengine[url]`."""

from __future__ import annotations

from md_generator.url.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
