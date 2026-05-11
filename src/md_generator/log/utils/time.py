from __future__ import annotations

from datetime import datetime

from dateutil import parser as du_parser


def parse_timestamp(
    text: str | None,
    *,
    fuzzy: bool = False,
) -> datetime | None:
    if text is None or not str(text).strip():
        return None
    try:
        return du_parser.parse(str(text).strip(), fuzzy=fuzzy)
    except (ValueError, TypeError, OverflowError):
        return None
