from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class YouTubeApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MD_YOUTUBE_",
        env_file=".env",
        extra="ignore",
    )

    job_ttl_seconds: int = 3600
    temp_dir: str | None = None
    cors_origins: str = "*"
    api_host: str = "127.0.0.1"
    api_port: int = 8013


def cors_list(settings: YouTubeApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
