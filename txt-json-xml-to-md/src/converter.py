from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.convert_impl import convert_text_file
from src.options import ConvertOptions


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert .txt, .json, or .xml to Markdown.")
    p.add_argument("input", type=Path, help="Input .txt, .json, or .xml path")
    p.add_argument("output", type=Path, help="Output .md file or directory (with --artifact-layout)")
    p.add_argument(
        "--artifact-layout",
        action="store_true",
        help="Write document.md under output directory",
    )
    p.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding for input (default: utf-8)",
    )
    p.add_argument(
        "--format",
        choices=("auto", "txt", "json", "xml"),
        default="auto",
        dest="input_format",
        help="Input format (default: auto from extension or sniff)",
    )
    p.add_argument(
        "--no-source-block",
        action="store_true",
        help="Do not append original JSON/XML in a fenced code block",
    )
    p.add_argument(
        "--toc",
        action="store_true",
        help="Insert a table of contents for JSON/XML section headings",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _options_from_args(ns: argparse.Namespace) -> ConvertOptions:
    return ConvertOptions(
        artifact_layout=ns.artifact_layout,
        verbose=ns.verbose,
        encoding=ns.encoding,
        input_format=ns.input_format,
        include_source_block=not ns.no_source_block,
        generate_toc=ns.toc,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    opts = _options_from_args(ns)
    inp = ns.input
    try:
        convert_text_file(inp, ns.output, opts)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        if opts.verbose:
            raise
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
