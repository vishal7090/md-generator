from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from src.options import InputFormat


def _strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _first_non_ws(text: str) -> str | None:
    m = re.search(r"\S", text)
    return m.group(0) if m else None


def _extension_hint(path: Path) -> InputFormat | None:
    suf = path.suffix.lower()
    if suf == ".json":
        return "json"
    if suf == ".xml":
        return "xml"
    if suf == ".txt":
        return "txt"
    return None


def detect_format(path: Path, text: str, override: InputFormat) -> InputFormat:
    text = _strip_bom(text)
    if override != "auto":
        return override
    ext = _extension_hint(path)
    if ext is not None:
        return ext
    ch = _first_non_ws(text)
    if ch in "{[":
        try:
            json.loads(text)
            return "json"
        except json.JSONDecodeError:
            pass
    if ch == "<":
        try:
            ET.fromstring(text)
            return "xml"
        except ET.ParseError:
            pass
    return "txt"
