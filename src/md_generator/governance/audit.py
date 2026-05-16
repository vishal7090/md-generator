from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_audit_block(*, tool: str, records: int, config_hash: str) -> dict[str, Any]:
    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "records_processed": records,
        "config_hash": config_hash,
    }
