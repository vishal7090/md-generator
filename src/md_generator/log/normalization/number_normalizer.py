from __future__ import annotations

import re

_NUM = re.compile(r"\b\d+\b")


def mask_numbers(text: str) -> str:
    return _NUM.sub("<NUM>", text)
