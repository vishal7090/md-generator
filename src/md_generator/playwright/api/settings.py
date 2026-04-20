from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PlaywrightApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLAYWRIGHT_TO_MD_",
        env_file=".env",
        extra="ignore",
    )

    max_sync_urls: int = 3
    max_job_urls: int = 20
    job_ttl_seconds: int = 3600
    temp_dir: str | None = None
    cors_origins: str = "*"
    api_host: str = "127.0.0.1"
    api_port: int = 8014


def cors_list(settings: PlaywrightApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
