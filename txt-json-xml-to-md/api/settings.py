from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TXT_JSON_XML_TO_MD_",
        env_file=".env",
        extra="ignore",
    )

    max_upload_mb: int = 200
    max_sync_upload_mb: int = 40
    job_ttl_seconds: int = 3600
    temp_dir: str | None = None
    cors_origins: str = "*"


def cors_list(settings: ApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
