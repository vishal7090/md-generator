from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_AWS_KEY = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")


def redact(text: str) -> str:
    text = _EMAIL.sub("<EMAIL>", text)
    text = _PHONE.sub("<PHONE>", text)
    text = _JWT.sub("<JWT>", text)
    text = _AWS_KEY.sub("<AWS_KEY>", text)
    return text
