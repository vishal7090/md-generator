"""CLI for image-to-md."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from md_generator.image.convert_impl import ConvertOptions, convert_images
from md_generator.image.utils import resolve_markdown_output


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert images to Markdown using one or more OCR engines.")
    p.add_argument("input", type=Path, help="Input image file or directory of images")
    p.add_argument("output", type=Path, help="Output .md path, or output directory with --artifact-layout")
    p.add_argument(
        "--artifact-layout",
        action="store_true",
        help="Treat OUTPUT as a directory and write document.md inside it",
    )
    p.add_argument(
        "--engines",
        type=str,
        default="tess,paddle,easy",
        help="Comma-separated engines: tess, paddle, easy (default: tess,paddle,easy)",
    )
    p.add_argument(
        "--strategy",
        choices=("compare", "best"),
        default="compare",
        help="compare: section per engine; best: longest non-empty text (tie: earlier engine wins)",
    )
    p.add_argument("--title", type=str, default="OCR extraction", help="Top-level Markdown heading")
    p.add_argument("--lang", type=str, default="eng", metavar="CODE", help="Tesseract language (default: eng)")
    p.add_argument(
        "--paddle-lang",
        type=str,
        default="en",
        metavar="CODE",
        help="PaddleOCR lang code (default: en)",
    )
    p.add_argument(
        "--paddle-no-angle-cls",
        action="store_true",
        help="Disable PaddleOCR angle classifier",
    )
    p.add_argument(
        "--easy-lang",
        type=str,
        default="en",
        help="Comma-separated EasyOCR language codes (default: en)",
    )
    p.add_argument(
        "--tesseract-cmd",
        type=str,
        default=None,
        help="Path to tesseract executable (default: env TESSERACT_CMD or TESSERACT_PATH)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Print dependency/runtime warnings to stderr")
    return p


def default_tesseract_cmd_from_env() -> str | None:
    return os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tess_cmd = args.tesseract_cmd or default_tesseract_cmd_from_env()
    easy_langs = tuple(s.strip() for s in str(args.easy_lang).split(",") if s.strip())
    if not easy_langs:
        easy_langs = ("en",)

    engines = tuple(x.strip().lower() for x in args.engines.split(",") if x.strip())
    if not engines:
        print("image-to-md: --engines must list at least one of tess, paddle, easy", file=sys.stderr)
        return 2

    out_md = resolve_markdown_output(args.output, artifact_layout=bool(args.artifact_layout))
    inp = Path(args.input)
    if not inp.exists():
        print(f"image-to-md: input not found: {inp}", file=sys.stderr)
        return 2

    opts = ConvertOptions(
        engines=engines,
        strategy=args.strategy,
        title=args.title,
        tess_lang=args.lang,
        tesseract_cmd=tess_cmd,
        paddle_lang=args.paddle_lang,
        paddle_use_angle_cls=not bool(args.paddle_no_angle_cls),
        easy_langs=easy_langs,
        verbose=bool(args.verbose),
    )

    try:
        convert_images(inp, out_md, opts)
    except ValueError as e:
        print(f"image-to-md: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"image-to-md: conversion failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
