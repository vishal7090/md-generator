from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MD_AUDIO_",
        env_file=".env",
        extra="ignore",
    )

    max_upload_mb: int = 200
    max_sync_upload_mb: int = 40
    job_ttl_seconds: int = 3600
    temp_dir: str | None = None
    cors_origins: str = "*"
    api_host: str = "127.0.0.1"
    api_port: int = 8011


def cors_list(settings: AudioApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
