from __future__ import annotations

import re

_REQ = re.compile(r"\brequest[_-]?id[=:]?\s*([\w-]+)", re.I)
_CORR = re.compile(r"\bcorrelation[_-]?id[=:]?\s*([\w-]+)", re.I)


def parse_request_fields(text: str) -> tuple[str | None, str | None]:
    rm = _REQ.search(text)
    cm = _CORR.search(text)
    return (rm.group(1) if rm else None, cm.group(1) if cm else None)
