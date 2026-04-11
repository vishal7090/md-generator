"""Shared OCR backend typing."""

from __future__ import annotations

from typing import Protocol

from PIL import Image


class OcrBackend(Protocol):
    """Run OCR on a PIL image (RGB)."""

    name: str

    def extract(self, image: Image.Image) -> str:
        """Return plain text (may be empty if OCR failed or dependency missing)."""
        ...
