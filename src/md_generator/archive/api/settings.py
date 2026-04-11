from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from md_generator.archive.options import DEFAULT_IMAGE_TO_MD_ENGINES


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZIP_TO_MD_",
        env_file=".env",
        extra="ignore",
    )

    max_upload_mb: int = 200
    max_sync_upload_mb: int = 40
    job_ttl_seconds: int = 3600
    temp_dir: str | None = None
    cors_origins: str = "*"
    """Deprecated: ignored; converters are imported from the md_generator package."""
    repo_root: str | None = None
    use_image_to_md: bool = True
    image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES
    image_to_md_strategy: str = "best"
    image_to_md_title: str = ""


def cors_list(settings: ApiSettings) -> list[str]:
    raw = (settings.cors_origins or "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
