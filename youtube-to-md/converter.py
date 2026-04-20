"""Shim CLI: prefer ``md-youtube`` after ``pip install mdengine[youtube]``."""

from __future__ import annotations

from md_generator.media.youtube.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
