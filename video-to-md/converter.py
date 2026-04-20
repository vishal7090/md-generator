"""Shim CLI: prefer `md-video` after `pip install mdengine[video]`."""

from __future__ import annotations

from md_generator.media.video.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
