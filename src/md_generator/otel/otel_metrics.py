from __future__ import annotations

from typing import Any


def parse_otlp_metrics(doc: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rsrc in doc.get("resourceMetrics", []) or []:
        for scope in rsrc.get("scopeMetrics", []) or []:
            for m in scope.get("metrics", []) or []:
                rows.append({"name": m.get("name"), "description": m.get("description")})
    return rows
