from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CodeflowApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CODEFLOW_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8016
    max_upload_zip_mb: int = 64
    max_sync_zip_mb: int = 8
    job_workspace_root: str | None = None
    sqlite_path: str | None = None


def cors_list(settings: CodeflowApiSettings) -> list[str]:
    raw = os.environ.get("CODEFLOW_CORS", "http://localhost:3000")
    return [x.strip() for x in raw.split(",") if x.strip()]


def sqlite_path_resolved(settings: CodeflowApiSettings) -> Path | None:
    if settings.sqlite_path:
        return Path(settings.sqlite_path)
    return None
