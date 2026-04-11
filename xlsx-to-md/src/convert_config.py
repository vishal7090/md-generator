from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

ExcelMaxRows: int = 1_048_576
Alignment = Literal["left", "right", "center"]
HeadingLevel = Literal["##", "###"]


@dataclass
class ConvertConfig:
    include_hidden_sheets: bool = False
    max_rows_per_sheet: int = ExcelMaxRows
    sheet_names: list[str] | None = None
    split_by_sheet: bool = False
    sheet_heading_level: HeadingLevel = "##"
    include_toc: bool = True
    column_indices: list[int] | None = None
    column_names: list[str] | None = None
    column_alignment: list[Alignment] = field(default_factory=list)
    enable_alignment_in_tables: bool = False
    expand_merged_cells: bool = True
    streaming: bool = False
    output_basename: str | None = None

    @classmethod
    def from_json(cls, path: Path | str) -> ConvertConfig:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConvertConfig:
        known = {f.name for f in fields(cls)}
        base = asdict(cls())
        for key, value in data.items():
            if key not in known:
                continue
            if key == "sheet_heading_level" and value is not None:
                if value not in ("##", "###"):
                    raise ValueError(f"sheet_heading_level must be '##' or '###', got {value!r}")
            if key == "column_alignment" and value is not None:
                for a in value:
                    if a not in ("left", "right", "center"):
                        raise ValueError(f"Invalid column_alignment value: {a!r}")
            base[key] = value
        return cls(**base)

    def merged_with_overrides(self, **overrides: Any) -> ConvertConfig:
        d = asdict(self)
        for k, v in overrides.items():
            if v is None:
                continue
            if k in d:
                d[k] = v
        return ConvertConfig(**d)
