"""Apply runtime edge counts to CFG ``runtime_prob`` (outgoing normalization per source).

**Trace JSON shape** (same as :func:`md_generator.codeflow.graph.hotpath.normalize_runtime_trace`):

- ``{"counts": {"u->v": number, ...}}`` — preferred key; ``edges`` is accepted as an alias in normalization.
- Each key is a string ``source_cfg_id + "->" + target_cfg_id`` for one directed CFG edge.
- Values are non-negative frequencies (coerced to ``float``); missing edges get no runtime weight.

Identifiers must match CFG node ids after IR expansion in this project.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from md_generator.codeflow.graph.cfg_model import CFG


def apply_runtime_weights(cfg: CFG, trace: dict[str, Any]) -> None:
    """Set ``edge.runtime_prob`` from ``trace["counts"]`` keys ``"source->target"``."""
    counts_raw = trace.get("counts") or {}
    counts: dict[str, float] = {}
    for k, v in counts_raw.items():
        try:
            counts[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    total_out: dict[str, float] = defaultdict(float)
    for key, cnt in counts.items():
        if "->" not in key:
            continue
        u, _v = key.split("->", 1)
        total_out[u] += cnt
    for e in cfg.edges:
        key = f"{e.source}->{e.target}"
        if key in counts:
            tot = total_out.get(e.source, 0.0)
            e.runtime_prob = counts[key] / max(tot, 1.0)
        else:
            e.runtime_prob = None
