"""PaddleOCR backend."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image


def _paddle_lines(result: object) -> list[str]:
    """Turn PaddleOCR `ocr()` output into stripped text lines."""
    lines: list[str] = []
    if not result or not isinstance(result, (list, tuple)) or not result[0]:
        return lines
    row0 = result[0]
    if not isinstance(row0, (list, tuple)):
        return lines
    for line in row0:
        if not line or len(line) < 2:
            continue
        chunk = line[1]
        if isinstance(chunk, (list, tuple)) and chunk:
            tx = str(chunk[0]).strip()
        else:
            tx = str(chunk).strip()
        if tx:
            lines.append(tx)
    return lines


class PaddleBackend:
    name = "PaddleOCR"

    def __init__(
        self,
        *,
        lang: str = "en",
        use_angle_cls: bool = True,
        verbose: bool = False,
    ) -> None:
        self._lang = lang
        self._use_angle_cls = use_angle_cls
        self._verbose = verbose
        self._ocr: Any = None

    def _ensure(self) -> bool:
        if self._ocr is not None:
            return True
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            if self._verbose:
                print(
                    "image-to-md: paddleocr not installed (see requirements-ocr.txt).",
                    file=sys.stderr,
                )
            return False
        try:
            self._ocr = PaddleOCR(
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                show_log=False,
            )
        except Exception as e:
            if self._verbose:
                print(f"image-to-md: PaddleOCR init failed: {e}", file=sys.stderr)
            return False
        return True

    def extract(self, image: Image.Image) -> str:
        if not self._ensure() or self._ocr is None:
            return ""
        try:
            import numpy as np
        except ImportError:
            if self._verbose:
                print("image-to-md: numpy required for PaddleOCR path.", file=sys.stderr)
            return ""
        try:
            arr = np.array(image.convert("RGB"))
            result = self._ocr.ocr(arr, cls=self._use_angle_cls)
            return "\n".join(_paddle_lines(result)).strip()
        except Exception as e:
            if self._verbose:
                print(f"image-to-md: PaddleOCR run failed: {e}", file=sys.stderr)
            return ""
