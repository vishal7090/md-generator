"""Shim CLI: prefer `md-audio` after `pip install mdengine[audio]`."""

from __future__ import annotations

from md_generator.media.audio.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
