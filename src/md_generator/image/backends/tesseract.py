"""Tesseract via pytesseract."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


class TesseractBackend:
    name = "Tesseract"

    def __init__(
        self,
        *,
        lang: str = "eng",
        tesseract_cmd: str | None = None,
        verbose: bool = False,
    ) -> None:
        self._lang = lang
        self._tesseract_cmd = tesseract_cmd
        self._verbose = verbose

    def extract(self, image: Image.Image) -> str:
        try:
            import pytesseract
        except ImportError:
            if self._verbose:
                print(
                    "image-to-md: pytesseract not installed (pip install pytesseract Pillow; "
                    "also install Tesseract OCR binary).",
                    file=sys.stderr,
                )
            return ""
        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
        try:
            text = pytesseract.image_to_string(image, lang=self._lang)
            return (text or "").strip()
        except Exception as e:
            if self._verbose:
                print(f"image-to-md: Tesseract OCR failed: {e}", file=sys.stderr)
            return ""
