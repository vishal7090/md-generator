"""Generate tests/fixtures/minimal.pdf (run manually or via conftest)."""

from __future__ import annotations

import base64
from pathlib import Path

import fitz

# 1x1 red PNG (valid)
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def build_minimal_pdf(dest: Path) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    try:
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((72, 100), "Fixture page one", fontsize=14)
        p1.insert_text((72, 130), "Body line for median size.", fontsize=11)
        p2 = doc.new_page(width=595, height=842)
        p2.insert_text((72, 100), "Fixture page two", fontsize=14)
        p2.insert_text((72, 130), "Second page body.", fontsize=11)
        p2.insert_image(fitz.Rect(72, 200, 120, 248), stream=_TINY_PNG)
        doc.save(dest.as_posix())
    finally:
        doc.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    build_minimal_pdf(root / "fixtures" / "minimal.pdf")
    print("Wrote tests/fixtures/minimal.pdf")
