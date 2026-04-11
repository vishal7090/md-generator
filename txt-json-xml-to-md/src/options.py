from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, Literal

InputFormat = Literal["auto", "txt", "json", "xml"]


@dataclass
class ConvertOptions:
    """CLI and API conversion flags."""

    artifact_layout: bool = False
    verbose: bool = False
    encoding: str = "utf-8"
    input_format: InputFormat = "auto"
    include_source_block: bool = True
    generate_toc: bool = False

    @classmethod
    def field_names(cls) -> set[str]:
        return {f.name for f in fields(cls)}

    def with_overrides(self, **kwargs: Any) -> ConvertOptions:
        known = self.field_names()
        clean = {k: v for k, v in kwargs.items() if k in known and v is not None}
        return replace(self, **clean)
