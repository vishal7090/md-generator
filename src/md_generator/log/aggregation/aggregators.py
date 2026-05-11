from __future__ import annotations

import pandas as pd

from md_generator.log.parser.models import LogRecord


def level_counts(records: list[LogRecord]) -> dict[str, int]:
    df = pd.DataFrame([{"level": r.level} for r in records])
    if df.empty:
        return {}
    return df["level"].value_counts().to_dict()


def top_messages(records: list[LogRecord], *, n: int = 20) -> list[tuple[str, int]]:
    df = pd.DataFrame([{"message": r.message[:500]} for r in records])
    if df.empty:
        return []
    vc = df["message"].value_counts().head(n)
    return [(str(k), int(v)) for k, v in vc.items()]
