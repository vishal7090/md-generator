"""OCR backend implementations."""

from __future__ import annotations

from src.backends.base import OcrBackend
from src.backends.easy import EasyOcrBackend
from src.backends.paddle import PaddleBackend
from src.backends.tesseract import TesseractBackend

__all__ = ["OcrBackend", "TesseractBackend", "PaddleBackend", "EasyOcrBackend"]
