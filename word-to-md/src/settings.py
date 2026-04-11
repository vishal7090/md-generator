from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float_mb(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw


@dataclass(frozen=True)
class WordToMdSettings:
    max_upload_mb: float
    max_sync_upload_mb: float
    job_ttl_seconds: int
    temp_dir: str
    cors_origins: tuple[str, ...]


def load_settings() -> WordToMdSettings:
    prefix = "WORD_TO_MD_"
    origins_raw = os.environ.get(f"{prefix}CORS_ORIGINS", "").strip()
    if origins_raw:
        cors_origins = tuple(o.strip() for o in origins_raw.split(",") if o.strip())
    else:
        cors_origins = ()

    return WordToMdSettings(
        max_upload_mb=_env_float_mb(f"{prefix}MAX_UPLOAD_MB", 200.0),
        max_sync_upload_mb=_env_float_mb(f"{prefix}MAX_SYNC_UPLOAD_MB", 40.0),
        job_ttl_seconds=_env_int(f"{prefix}JOB_TTL_SECONDS", 3600),
        temp_dir=_env_str(f"{prefix}TEMP_DIR", tempfile.gettempdir()),
        cors_origins=cors_origins,
    )
