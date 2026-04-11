from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from pathlib import Path

from md_generator.xlsx.convert_config import ConvertConfig
from md_generator.xlsx.excel_reader import iter_sheet_rows
from md_generator.xlsx.markdown_emitter import rows_to_gfm_table, safe_filename_slug, slugify_sheet_title

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".xlsx", ".xlsm", ".csv"}


@dataclass
class ConvertResult:
    paths_written: list[Path] = field(default_factory=list)
    sheets_processed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log_text: str = ""


def _validate_input(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Input not found: {path}")
    suf = path.suffix.casefold()
    if suf not in ALLOWED_SUFFIXES:
        raise ValueError(f"Expected .xlsx, .xlsm, or .csv file, got {path.suffix!r}")


def _sheet_html_heading(title: str, sheet_heading_level: str) -> tuple[str, str]:
    slug = slugify_sheet_title(title)
    tag = "h2" if sheet_heading_level == "##" else "h3"
    line = f'<{tag} id="{slug}">Sheet: {html.escape(title)}</{tag}>\n\n'
    return line, slug


def _build_toc(slugs_titles: list[tuple[str, str]]) -> str:
    lines = ["## Table of contents", ""]
    for slug, title in slugs_titles:
        lines.append(f"- [{title}](#{slug})")
    lines.append("")
    return "\n".join(lines)


def convert_excel_to_markdown(
    input_path: Path,
    output_dir: Path,
    *,
    split_by_sheet: bool | None = None,
    config: ConvertConfig | None = None,
) -> ConvertResult:
    cfg = config or ConvertConfig()
    if split_by_sheet is not None:
        cfg = cfg.merged_with_overrides(split_by_sheet=split_by_sheet)

    result = ConvertResult()
    warnings = result.warnings
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    _validate_input(input_path)

    output_dir.mkdir(parents=True, exist_ok=True)

    sheets_data: list[tuple[str, str]] = []

    for sheet_title, matrix in iter_sheet_rows(
        input_path,
        streaming=cfg.streaming,
        expand_merged_cells=cfg.expand_merged_cells,
        include_hidden_sheets=cfg.include_hidden_sheets,
        sheet_names=cfg.sheet_names,
        max_rows_per_sheet=cfg.max_rows_per_sheet,
        warnings=warnings,
    ):
        table = rows_to_gfm_table(
            matrix,
            column_names=cfg.column_names,
            column_indices=cfg.column_indices,
            column_alignment=cfg.column_alignment,
            enable_alignment_in_tables=cfg.enable_alignment_in_tables,
        )
        if not table:
            warnings.append(f"Sheet {sheet_title!r} produced no table rows (empty or filtered).")
            logger.info("Skipping empty table for sheet %s", sheet_title)
            continue

        result.sheets_processed.append(sheet_title)

        if cfg.split_by_sheet:
            fname = safe_filename_slug(sheet_title) + ".md"
            out_path = output_dir / fname
            block = f"# Sheet: {sheet_title}\n\n{table}\n"
            out_path.write_text(block, encoding="utf-8")
            result.paths_written.append(out_path)
        else:
            heading, slug = _sheet_html_heading(sheet_title, cfg.sheet_heading_level)
            sheets_data.append((heading + table, slug, sheet_title))

    if not cfg.split_by_sheet and sheets_data:
        toc_block = ""
        if cfg.include_toc and len(sheets_data) > 1:
            toc_block = _build_toc([(s[1], s[2]) for s in sheets_data])

        stem = (cfg.output_basename or input_path.stem).replace("/", "-").replace("\\", "-")
        if not stem.endswith(".md"):
            out_name = f"{stem}.md"
        else:
            out_name = stem
        out_path = output_dir / out_name

        body = "".join(s[0] + "\n\n" for s in sheets_data)
        combined = f"{toc_block}{body}".rstrip() + "\n"
        out_path.write_text(combined, encoding="utf-8")
        result.paths_written.append(out_path)

    log_path = output_dir / "conversion_log.txt"
    if log_path not in result.paths_written:
        result.paths_written.append(log_path)

    log_lines = [
        f"Input: {input_path}",
        f"Output directory: {output_dir}",
        f"Sheets processed: {', '.join(result.sheets_processed) or '(none)'}",
        f"Files written: {len(result.paths_written)}",
    ]
    if warnings:
        log_lines.append("Warnings:")
        log_lines.extend(f"  - {w}" for w in warnings)
    result.log_text = "\n".join(log_lines) + "\n"
    log_path.write_text(result.log_text, encoding="utf-8")

    return result
