from __future__ import annotations

from typing import Any


def retention_metadata(*, days: int = 90) -> dict[str, Any]:
    return {"retention_days": days, "policy": "operational_logs"}
