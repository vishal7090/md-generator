from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.convert_config import ConvertConfig
from src.converter_core import convert_excel_to_markdown


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert Excel workbooks (.xlsx, .xlsm) to Markdown.")
    p.add_argument("-i", "--input", required=True, type=Path, help="Path to .xlsx or .xlsm file")
    p.add_argument("-o", "--output-dir", required=True, type=Path, help="Output directory")
    p.add_argument("--config", type=Path, default=None, help="JSON ConvertConfig file")
    p.add_argument("--split", action="store_true", help="One .md file per worksheet")
    p.add_argument("--include-hidden-sheets", action="store_true", help="Include hidden worksheets")
    p.add_argument("--no-toc", action="store_true", help="Omit table of contents (combined mode)")
    p.add_argument("--streaming", action="store_true", help="Read-only OpenPyXL mode (no merged expansion)")
    p.add_argument("--no-expand-merged", action="store_true", help="Do not fill merged cell ranges")
    p.add_argument("--max-rows", type=int, default=None, metavar="N", help="Max rows per sheet")
    p.add_argument(
        "--sheet",
        action="append",
        default=None,
        dest="sheets",
        metavar="NAME",
        help="Export only sheet(s) with this name (repeatable, case-insensitive)",
    )
    p.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))

    cfg = ConvertConfig.from_json(args.config) if args.config else ConvertConfig()
    if args.split:
        cfg = cfg.merged_with_overrides(split_by_sheet=True)
    if args.include_hidden_sheets:
        cfg = cfg.merged_with_overrides(include_hidden_sheets=True)
    if args.no_toc:
        cfg = cfg.merged_with_overrides(include_toc=False)
    if args.streaming:
        cfg = cfg.merged_with_overrides(streaming=True)
    if args.no_expand_merged:
        cfg = cfg.merged_with_overrides(expand_merged_cells=False)
    if args.max_rows is not None:
        cfg = cfg.merged_with_overrides(max_rows_per_sheet=args.max_rows)
    if args.sheets:
        cfg = cfg.merged_with_overrides(sheet_names=list(args.sheets))

    try:
        result = convert_excel_to_markdown(args.input, args.output_dir, config=cfg)
    except (OSError, ValueError) as e:
        logging.error("%s", e)
        return 1
    for w in result.warnings:
        logging.warning("%s", w)
    logging.info("Wrote %s", ", ".join(str(p) for p in result.paths_written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
