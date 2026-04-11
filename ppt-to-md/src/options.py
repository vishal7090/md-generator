from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any


@dataclass
class ConvertOptions:
    """CLI and API conversion flags (README parity)."""

    artifact_layout: bool = False
    images_dir: Path | None = None

    title_slide_h1: bool = True
    strip_known_footers: bool = True
    verbose: bool = False

    max_unpack_depth: int = 2
    chart_data: bool = True
    chart_image: bool = True
    table_csv: bool = True
    extract_embedded_deep: bool = True

    emit_extracted_txt_md: bool = True
    extracted_docx_md: bool = True
    extracted_pdf_md: bool = True
    extracted_xlsx_md: bool = True
    extracted_pdf_ocr: bool = True
    extracted_pdf_ocr_min_chars: int = 50

    @classmethod
    def field_names(cls) -> set[str]:
        return {f.name for f in fields(cls)}

    def with_overrides(self, **kwargs: Any) -> ConvertOptions:
        known = self.field_names()
        clean = {k: v for k, v in kwargs.items() if k in known and v is not None}
        return replace(self, **clean)
