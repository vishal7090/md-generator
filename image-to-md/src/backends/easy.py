"""EasyOCR backend."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image


class EasyOcrBackend:
    name = "EasyOCR"

    def __init__(self, *, langs: tuple[str, ...] = ("en",), verbose: bool = False) -> None:
        self._langs = list(langs) if langs else ["en"]
        self._verbose = verbose
        self._reader: Any = None

    def _ensure(self) -> bool:
        if self._reader is not None:
            return True
        try:
            import easyocr
        except ImportError:
            if self._verbose:
                print(
                    "image-to-md: easyocr not installed (see requirements-ocr.txt).",
                    file=sys.stderr,
                )
            return False
        try:
            self._reader = easyocr.Reader(self._langs)
        except Exception as e:
            if self._verbose:
                print(f"image-to-md: EasyOCR init failed: {e}", file=sys.stderr)
            return False
        return True

    def extract(self, image: Image.Image) -> str:
        if not self._ensure() or self._reader is None:
            return ""
        try:
            import numpy as np
        except ImportError:
            if self._verbose:
                print("image-to-md: numpy required for EasyOCR path.", file=sys.stderr)
            return ""
        try:
            arr = np.array(image.convert("RGB"))
            parts = self._reader.readtext(arr, detail=0, paragraph=False)
            if not parts:
                return ""
            if isinstance(parts, str):
                return parts.strip()
            return "\n".join(str(p).strip() for p in parts if str(p).strip()).strip()
        except Exception as e:
            if self._verbose:
                print(f"image-to-md: EasyOCR run failed: {e}", file=sys.stderr)
            return ""
