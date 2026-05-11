from __future__ import annotations

from datetime import datetime

from md_generator.log.utils.time import parse_timestamp


def parse_log_timestamp(text: str | None, *, fuzzy: bool) -> datetime | None:
    return parse_timestamp(text, fuzzy=fuzzy)
