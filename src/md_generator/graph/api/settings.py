from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPH_TO_MD_",
        env_file=".env",
        extra="ignore",
    )

    job_sqlite_path: str | None = None
    job_workspace_root: str | None = None
    cors_origins: str = "*"
    max_sync_zip_mb: int = 80


def cors_list(settings: GraphApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def sqlite_path_resolved(settings: GraphApiSettings) -> Path | None:
    if settings.job_sqlite_path:
        return Path(settings.job_sqlite_path)
    return None
