from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.convert_impl import convert_zip
from src.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert .zip archive to Markdown + assets (artifact layout).")
    p.add_argument("input", type=Path, help="Input .zip path")
    p.add_argument("output", type=Path, help="Output directory (writes document.md and assets/)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--no-office", action="store_true", help="Skip PDF/DOCX/PPTX/XLSX subprocess conversion")
    p.add_argument("--image-ocr", dest="image_ocr", action="store_true", help="Run tesseract on extracted images")
    p.add_argument("--no-image-ocr", dest="image_ocr", action="store_false")
    p.set_defaults(image_ocr=False)
    p.add_argument(
        "--use-image-to-md",
        dest="use_image_to_md",
        action="store_true",
        help="Enable post-pass image-to-md OCR (default: on); see --image-to-md-engines",
    )
    p.add_argument(
        "--no-use-image-to-md",
        dest="use_image_to_md",
        action="store_false",
        help="Disable post-pass image-to-md over assets/files and assets/images",
    )
    p.set_defaults(use_image_to_md=True)
    p.add_argument(
        "--image-to-md-engines",
        type=str,
        default=DEFAULT_IMAGE_TO_MD_ENGINES,
        metavar="LIST",
        help=f"Comma-separated OCR engines for image-to-md: tess, paddle, easy (default: {DEFAULT_IMAGE_TO_MD_ENGINES})",
    )
    p.add_argument(
        "--image-to-md-strategy",
        choices=("best", "compare"),
        default="best",
        help="image-to-md --strategy (default: best)",
    )
    p.add_argument(
        "--image-to-md-title",
        type=str,
        default="",
        metavar="TEXT",
        help="Top-level title passed to image-to-md (default: derived from filename)",
    )
    p.add_argument("--pdf-ocr", action="store_true", help="Pass --ocr to pdf-to-md for nested PDFs")
    p.add_argument(
        "--max-bytes",
        type=int,
        default=512_000,
        metavar="N",
        help="Max UTF-8 bytes for inlined text bodies (default: 512000)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Parent directory containing word-to-md, pdf-to-md, etc. (default: parent of zip-to-md or MD_GENERATOR_ROOT)",
    )
    p.add_argument(
        "--no-expand-nested-zips",
        action="store_true",
        help="Do not recursively extract .zip members under assets/files/",
    )
    p.add_argument(
        "--max-nested-zip-depth",
        type=int,
        default=16,
        metavar="N",
        help="Max nesting depth for inner ZIPs (each *_unzipped/ segment counts as one level; default: 16)",
    )
    return p


def _options_from_args(ns: argparse.Namespace) -> ConvertOptions:
    return ConvertOptions(
        verbose=ns.verbose,
        artifact_layout=True,
        enable_office=not ns.no_office,
        image_ocr=ns.image_ocr,
        pdf_ocr=ns.pdf_ocr,
        max_bytes=ns.max_bytes,
        repo_root=str(ns.repo_root.resolve()) if ns.repo_root is not None else None,
        expand_nested_zips=not ns.no_expand_nested_zips,
        max_nested_zip_depth=max(1, int(ns.max_nested_zip_depth)),
        use_image_to_md=ns.use_image_to_md,
        image_to_md_engines=str(ns.image_to_md_engines).strip() or DEFAULT_IMAGE_TO_MD_ENGINES,
        image_to_md_strategy=str(ns.image_to_md_strategy),
        image_to_md_title=str(ns.image_to_md_title or "").strip(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    opts = _options_from_args(ns)
    inp = ns.input
    if inp.suffix.lower() != ".zip":
        print("Input must be a .zip file", file=sys.stderr)
        return 2
    out = ns.output
    if out.exists() and not out.is_dir():
        print("Output must be a directory", file=sys.stderr)
        return 2
    try:
        convert_zip(inp, out, opts)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        if opts.verbose:
            raise
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
