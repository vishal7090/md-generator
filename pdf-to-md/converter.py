"""Shim CLI: prefer `md-pdf` or `python -m md_generator.pdf.converter` after `pip install -e .`"""

from __future__ import annotations

from md_generator.pdf.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
