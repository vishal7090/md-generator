"""Build normalized CFG runtime trace JSON from explicit edge observations.

Output shape matches :func:`md_generator.codeflow.graph.hotpath.normalize_runtime_trace` /
:func:`md_generator.codeflow.graph.runtime_integration.apply_runtime_weights`:

- JSON object with a ``counts`` mapping (``edges`` is an equivalent alias elsewhere).
- Keys: ``"source_cfg_id->target_cfg_id"`` (literal ``->`` separator).
- Values: non-negative numeric frequencies.

Identifiers must match CFG node ids from IR expansion (same strings as ``cfg.json`` sidecars).
This module does not attach a full ``sys.settrace``; callers record pairs they care about.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class PythonEdgeCounter:
    """Increment directed CFG edge keys for export as runtime trace JSON."""

    def __init__(self) -> None:
        self._weights: dict[tuple[str, str], float] = defaultdict(float)

    def record(self, source: str, target: str, weight: float = 1.0) -> None:
        self._weights[(str(source), str(target))] += float(weight)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "counts": {f"{u}->{v}": w for (u, v), w in self._weights.items()},
        }


def trace_from_pairs(pairs: list[tuple[str, str]], weights: list[float] | None = None) -> dict[str, Any]:
    """Build a trace dict from parallel lists of (source, target) and optional weights."""
    c = PythonEdgeCounter()
    if not weights:
        for u, v in pairs:
            c.record(u, v)
    else:
        for i, (u, v) in enumerate(pairs):
            c.record(u, v, weights[i] if i < len(weights) else 1.0)
    return c.to_trace_dict()
