from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class ScanConfig:
    """Input and output options for a codeflow scan."""

    project_root: Path
    output_path: Path
    paths_override: list[Path] | None = None
    formats: tuple[str, ...] = ("md", "mermaid", "json")
    depth: int = 5
    languages: str = "mixed"  # mixed|python|java|javascript|typescript|tsx|cpp|go|php|comma list
    entry: list[str] | None = None
    include: str | None = None  # api,event,main,...
    exclude: str | None = None
    include_internal: bool = True
    async_mode: bool = True
    jobs: bool = False
    runtime: bool = False
    business_rules: bool = True
    business_rules_sql: bool = False
    business_rules_combined: bool = True
    # Entry resolution: ``none`` = no heuristic roots when nothing detected; ``roots`` = in-degree 0 symbols; ``first_n`` = lexicographic first nodes (legacy-ish).
    entry_fallback: Literal["none", "roots", "first_n"] = "roots"
    entry_fallback_max: int = 20
    emit_entry_per_method: bool = False
    emit_entry_max: int | None = None
    emit_entry_filter: str | None = None
    entries_file: Path | None = None
    write_scan_summary: bool = True

    def parsed_include(self) -> set[str] | None:
        if not self.include or not str(self.include).strip():
            return None
        return {x.strip() for x in str(self.include).split(",") if x.strip()}
