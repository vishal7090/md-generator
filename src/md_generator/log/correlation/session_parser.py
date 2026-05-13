from __future__ import annotations

import re

_SESSION = re.compile(r"\bsession[_-]?id[=:]?\s*([\w-]+)", re.I)


def parse_session_id(text: str) -> str | None:
    m = _SESSION.search(text)
    return m.group(1) if m else None
