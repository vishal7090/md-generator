from __future__ import annotations

import json
from typing import Any


def format_sse(event: str, payload: dict[str, Any]) -> str:
    """Format one SSE message (event + JSON data line)."""
    return f"event: {event}\ndata: {json.dumps(payload, sort_keys=True)}\n\n"
