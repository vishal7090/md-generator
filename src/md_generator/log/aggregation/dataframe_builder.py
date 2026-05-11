from __future__ import annotations

import pandas as pd

from md_generator.log.parser.models import LogRecord


def records_to_dataframe(records: list[LogRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append(
            {
                "timestamp": r.timestamp,
                "level": r.level,
                "logger": r.logger,
                "thread": r.thread,
                "message": r.message,
                "source_file": str(r.source_file),
                "line_number": r.line_number,
                "correlation_id": r.correlation_id,
                "fingerprint": r.fingerprint,
            },
        )
    return pd.DataFrame(rows)


def add_time_bucket(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty or "timestamp" not in df.columns:
        return df
    out = df.copy()
    ts = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out["_ts"] = ts
    if rule == "hourly":
        out["time_bucket"] = ts.dt.floor("h")
    elif rule == "daily":
        out["time_bucket"] = ts.dt.floor("D")
    else:
        out["time_bucket"] = pd.NaT
    return out
