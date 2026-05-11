from __future__ import annotations

import pandas as pd

from md_generator.log.aggregation.dataframe_builder import add_time_bucket, records_to_dataframe
from md_generator.log.parser.models import LogRecord


def hourly_timeline(records: list[LogRecord]) -> pd.DataFrame:
    df = records_to_dataframe(records)
    if df.empty:
        return df
    df = add_time_bucket(df, "hourly")
    g = df.dropna(subset=["time_bucket"]).groupby("time_bucket", dropna=True).size()
    return g.reset_index(name="count")
