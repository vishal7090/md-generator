"""CLI for pdf-to-md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.pdf_extract import ConvertOptions, convert_pdf
from src.utils import resolve_output


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert PDF to Markdown.")
    p.add_argument("input_pdf", type=Path, help="Input .pdf path")
    p.add_argument("output", type=Path, help="Output .md path or directory with --artifact-layout")
    p.add_argument(
        "--artifact-layout",
        action="store_true",
        help="Write OUTPUT/document.md and OUTPUT/assets/images/",
    )
    p.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Image directory (classic mode only; default: <parent of output.md>/images)",
    )
    p.add_argument("--ocr", action="store_true", help="OCR pages with little embedded text")
    p.add_argument(
        "--ocr-min-chars",
        type=int,
        default=40,
        metavar="N",
        help="Embedded text below this length triggers OCR when --ocr (default: 40)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Print warnings to stderr")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    opts = ConvertOptions(
        use_ocr=bool(args.ocr),
        ocr_min_chars=int(args.ocr_min_chars),
        verbose=bool(args.verbose),
    )
    if args.artifact_layout and args.images_dir is not None:
        print(
            "pdf-to-md: --images-dir is ignored with --artifact-layout",
            file=sys.stderr,
        )
    resolved = resolve_output(
        args.output,
        artifact_layout=bool(args.artifact_layout),
        images_dir=args.images_dir if not args.artifact_layout else None,
    )
    inp = Path(args.input_pdf)
    if not inp.is_file():
        print(f"pdf-to-md: input not found: {inp}", file=sys.stderr)
        return 2
    try:
        convert_pdf(inp, resolved, opts)
    except Exception as e:
        print(f"pdf-to-md: conversion failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
