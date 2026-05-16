from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from md_generator.runtime.execution_context import ExecutionContext


@contextmanager
def stage_timer(ctx: ExecutionContext, name: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        ctx.stage_timings_ms[name] = ctx.stage_timings_ms.get(name, 0) + ms


def merge_runtime_metrics(meta: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
    out = dict(meta)
    out["runtime"] = {
        "stage_timings_ms": dict(ctx.stage_timings_ms),
        "stage_counts": dict(ctx.stage_counts),
    }
    return out
