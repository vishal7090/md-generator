from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.ppt.convert_impl import convert_pptx
from md_generator.ppt.options import ConvertOptions


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert .pptx to Markdown.")
    p.add_argument("input", type=Path, help="Input .pptx path")
    p.add_argument("output", type=Path, help="Output .md file or directory (with --artifact-layout)")
    p.add_argument("--artifact-layout", action="store_true", help="Write document.md + assets/ under output dir")
    p.add_argument("--images-dir", type=Path, default=None, help="Image directory (classic mode only)")
    p.add_argument("--no-title-slide-h1", action="store_true", help="Use ## for all slide titles (classic)")
    p.add_argument("--no-strip-known-footers", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")

    p.add_argument("--max-unpack-depth", type=int, default=2)
    p.add_argument("--no-chart-data", action="store_true")
    p.add_argument("--no-chart-image", action="store_true")
    p.add_argument("--no-table-csv", action="store_true")
    p.add_argument("--extract-embedded-deep", dest="extract_embedded_deep", action="store_true")
    p.add_argument("--no-extract-embedded-deep", dest="extract_embedded_deep", action="store_false")
    p.set_defaults(extract_embedded_deep=True)

    p.add_argument("--no-extracted-txt-md", action="store_true")
    p.add_argument("--no-extracted-docx-md", action="store_true")
    p.add_argument("--no-extracted-pdf-md", action="store_true")
    p.add_argument("--no-extracted-xlsx-md", action="store_true")
    p.add_argument("--extracted-pdf-ocr", dest="extracted_pdf_ocr", action="store_true")
    p.add_argument("--no-extracted-pdf-ocr", dest="extracted_pdf_ocr", action="store_false")
    p.set_defaults(extracted_pdf_ocr=True)
    p.add_argument("--extracted-pdf-ocr-min-chars", type=int, default=50)

    return p


def _options_from_args(ns: argparse.Namespace) -> ConvertOptions:
    return ConvertOptions(
        artifact_layout=ns.artifact_layout,
        images_dir=ns.images_dir,
        title_slide_h1=not ns.no_title_slide_h1,
        strip_known_footers=not ns.no_strip_known_footers,
        verbose=ns.verbose,
        max_unpack_depth=ns.max_unpack_depth,
        chart_data=not ns.no_chart_data,
        chart_image=not ns.no_chart_image,
        table_csv=not ns.no_table_csv,
        extract_embedded_deep=ns.extract_embedded_deep,
        emit_extracted_txt_md=not ns.no_extracted_txt_md,
        extracted_docx_md=not ns.no_extracted_docx_md,
        extracted_pdf_md=not ns.no_extracted_pdf_md,
        extracted_xlsx_md=not ns.no_extracted_xlsx_md,
        extracted_pdf_ocr=ns.extracted_pdf_ocr,
        extracted_pdf_ocr_min_chars=ns.extracted_pdf_ocr_min_chars,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    opts = _options_from_args(ns)
    inp = ns.input
    if inp.suffix.lower() != ".pptx":
        print("Input must be a .pptx file", file=sys.stderr)
        return 2
    try:
        convert_pptx(inp, ns.output, opts)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        if opts.verbose:
            raise
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
