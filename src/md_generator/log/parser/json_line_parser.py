from __future__ import annotations

import json
from typing import Any


def try_parse_json_log_line(line: str) -> dict[str, Any] | None:
    """Parse a single JSON log line into structured fields."""
    text = line.strip()
    if not text or text[0] not in "{[":
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    log_obj = obj.get("log") if isinstance(obj.get("log"), dict) else {}
    level = obj.get("level") or obj.get("severity") or obj.get("severityText") or log_obj.get("level")
    if isinstance(level, dict):
        level = level.get("name") or level.get("severity")
    message = obj.get("message") or obj.get("msg") or obj.get("body") or log_obj.get("message")
    ts = (
        obj.get("timestamp")
        or obj.get("@timestamp")
        or obj.get("time")
        or obj.get("date")
    )
    logger = obj.get("logger") or obj.get("logger_name") or obj.get("name")
    thread = obj.get("thread") or obj.get("threadName")
    user = obj.get("user") or obj.get("username") or obj.get("screenname")
    ip = obj.get("ip") or obj.get("client_ip") or obj.get("remote_addr") or obj.get("clientip")
    user_obj = obj.get("user")
    if isinstance(user_obj, dict):
        user = user or user_obj.get("name") or user_obj.get("id")
    source_obj = obj.get("source")
    if isinstance(source_obj, dict):
        ip = ip or source_obj.get("ip")
    fields = obj.get("fields") if isinstance(obj.get("fields"), dict) else {}
    if isinstance(fields, dict):
        user = user or fields.get("screenname") or fields.get("user")
        ip = ip or fields.get("ip")
    attrs = obj.get("attributes") if isinstance(obj.get("attributes"), dict) else {}
    if isinstance(attrs, dict):
        user = user or attrs.get("user") or attrs.get("enduser.id")
        ip = ip or attrs.get("ip") or attrs.get("client.address")
    msg_parts = [str(message or "").strip()]
    if user:
        msg_parts.append(f"user={user}")
    if ip:
        msg_parts.append(f"ip={ip}")
    return {
        "timestamp": str(ts) if ts is not None else "",
        "level": str(level or "INFO").upper(),
        "logger": str(logger) if logger else None,
        "thread": str(thread) if thread else None,
        "message": " ".join(p for p in msg_parts if p),
        "_json": obj,
    }
