from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenapiToMdSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENAPI_TO_MD_",
        env_file=".env",
        extra="ignore",
    )

    cors_origins: str = "*"
    max_sync_zip_mb: int = 80


def cors_list(settings: OpenapiToMdSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
