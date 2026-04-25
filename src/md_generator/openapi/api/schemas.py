from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from md_generator.openapi.core.run_config import ApiRunConfig


class OpenapiGenerateOptions(BaseModel):
    """Optional JSON fields when using programmatic clients (multipart + JSON part)."""

    formats: list[str] = Field(default_factory=lambda: ["md", "mermaid", "html"])
    preferred_media_type: str = "application/json"

    def to_partial_config(self) -> dict[str, Any]:
        return {
            "formats": tuple(self.formats),
            "preferred_media_type": self.preferred_media_type,
        }


def merge_upload_config(tmp_file: Any, options: OpenapiGenerateOptions | None) -> ApiRunConfig:
    from pathlib import Path

    opts = options or OpenapiGenerateOptions()
    partial = opts.to_partial_config()
    return ApiRunConfig(
        file=Path(tmp_file),
        output_path=Path("."),
        formats=partial["formats"],
        preferred_media_type=str(partial["preferred_media_type"]),
    ).normalized()
