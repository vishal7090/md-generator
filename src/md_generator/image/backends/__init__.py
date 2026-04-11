"""OCR backend implementations."""

from __future__ import annotations

from md_generator.image.backends.base import OcrBackend
from md_generator.image.backends.easy import EasyOcrBackend
from md_generator.image.backends.paddle import PaddleBackend
from md_generator.image.backends.tesseract import TesseractBackend

__all__ = ["OcrBackend", "TesseractBackend", "PaddleBackend", "EasyOcrBackend"]
