from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def try_mermaid_py_png_svg(diagram: str, stem: Path) -> bool:
    """
    Render PNG and SVG via ``mermaid-py`` (mermaid.ink by default).
    Returns True if both files were written.
    """
    try:
        from mermaid import Mermaid
    except ImportError:
        logger.info("mermaid-py not installed; ERD will be Mermaid text only (.mermaid / .md).")
        return False
    stem.parent.mkdir(parents=True, exist_ok=True)
    try:
        m = Mermaid(diagram)
        m.to_png(stem.with_suffix(".png"))
        m.to_svg(stem.with_suffix(".svg"))
        return True
    except Exception as e:
        logger.warning("mermaid-py render failed (offline or mermaid.ink error): %s", e)
        return False
