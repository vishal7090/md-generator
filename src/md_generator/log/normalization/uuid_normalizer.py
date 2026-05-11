from __future__ import annotations

import re

_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
)


def mask_uuids(text: str) -> str:
    return _UUID.sub("<UUID>", text)
