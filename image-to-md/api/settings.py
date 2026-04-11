"""Environment limits (prefix IMAGE_TO_MD_)."""

from __future__ import annotations

import os
from typing import List


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(f"IMAGE_TO_MD_{name}")
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def max_upload_mb() -> int:
    return _get_int("MAX_UPLOAD_MB", 200)


def max_sync_upload_mb() -> int:
    return _get_int("MAX_SYNC_UPLOAD_MB", 40)


def job_ttl_seconds() -> int:
    return _get_int("JOB_TTL_SECONDS", 3600)


def temp_dir() -> str | None:
    v = os.environ.get("IMAGE_TO_MD_TEMP_DIR")
    return v if v else None


def cors_origins() -> List[str]:
    raw = os.environ.get("IMAGE_TO_MD_CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def tesseract_cmd() -> str | None:
    return os.environ.get("IMAGE_TO_MD_TESSERACT_CMD") or os.environ.get("TESSERACT_CMD")
