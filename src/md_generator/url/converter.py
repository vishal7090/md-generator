from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from md_generator.url.convert_impl import convert_url, convert_urls_from_list
from md_generator.url.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions


def _is_http_url(s: str) -> bool:
    p = urlparse(s.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert public HTTP(S) pages to Markdown.")
    p.add_argument("url", nargs="?", help="Single HTTP or HTTPS URL")
    p.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Output .md file or directory (with --artifact-layout); omit when using --urls-file with -o",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for --urls-file (bulk) mode",
    )
    p.add_argument("--urls-file", type=Path, default=None, help="Text file with one URL per line")
    p.add_argument("--artifact-layout", action="store_true", help="Write document.md + assets/ under output dir")
    p.add_argument("--crawl", action="store_true", help="Breadth-first crawl (requires --artifact-layout)")
    p.add_argument(
        "--async-crawl",
        action="store_true",
        help="Use async HTTP + parallel page fetches (requires --crawl); default is sync crawl",
    )
    p.add_argument(
        "--crawl-max-concurrency",
        type=int,
        default=4,
        help="Max concurrent page fetches when --async-crawl (default: 4, max: 32)",
    )
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--max-pages", type=int, default=30)
    p.add_argument("--crawl-delay", type=float, default=0.5, help="Seconds between crawl requests")
    p.add_argument("--no-robots", action="store_true", help="Do not consult robots.txt")
    p.add_argument("--no-subdomains", action="store_true", help="Only exact same host when following links")
    p.add_argument("--images-dir", type=Path, default=None, help="Classic mode: image directory (default: <md parent>/images)")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--max-response-mb", type=float, default=10.0)
    p.add_argument("--no-table-csv", action="store_true")
    p.add_argument("--no-linked-files", action="store_true", help="Skip downloading linked PDF/ZIP/etc.")
    p.add_argument(
        "--max-linked-files",
        type=int,
        default=40,
        help="Max linked file downloads per page (default: 40)",
    )
    p.add_argument(
        "--max-downloaded-images",
        type=int,
        default=50,
        help="Max image downloads per page (default: 50)",
    )
    p.add_argument(
        "--no-convert-downloaded-assets",
        action="store_true",
        help="Do not run internal converters on files under assets/files/",
    )
    p.add_argument(
        "--no-convert-downloaded-images",
        action="store_true",
        help="Skip OCR for raster images under assets/images/ (default: run when mdengine[image] is installed)",
    )
    p.add_argument(
        "--convert-downloaded-image-to-md-engines",
        type=str,
        default=DEFAULT_IMAGE_TO_MD_ENGINES,
        metavar="ENGINES",
        help="Comma-separated OCR engines for downloaded images: tess, paddle, easy (default: %(default)s)",
    )
    p.add_argument(
        "--convert-downloaded-image-to-md-strategy",
        type=str,
        choices=("best", "compare"),
        default="best",
        help='How to combine engine outputs for downloaded images (default: "best")',
    )
    p.add_argument(
        "--convert-downloaded-image-to-md-title",
        type=str,
        default="",
        help='Markdown title inside the bundled OCR file (default: empty → "Downloaded images (OCR)")',
    )
    p.add_argument(
        "--post-convert-pdf-ocr",
        action="store_true",
        help="When converting downloaded PDFs, enable page OCR like md-pdf --ocr",
    )
    p.add_argument(
        "--no-post-convert-ppt-embedded",
        action="store_true",
        help="When converting downloaded PPTX, disable deep embedded extraction",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _options_from_args(ns: argparse.Namespace) -> ConvertOptions:
    return ConvertOptions(
        artifact_layout=ns.artifact_layout,
        images_dir=ns.images_dir,
        verbose=ns.verbose,
        timeout_seconds=ns.timeout,
        max_response_bytes=int(ns.max_response_mb * 1024 * 1024),
        table_csv=not ns.no_table_csv,
        download_linked_files=not ns.no_linked_files,
        crawl=ns.crawl,
        async_crawl=ns.async_crawl,
        crawl_max_concurrency=ns.crawl_max_concurrency,
        max_depth=ns.max_depth,
        max_pages=ns.max_pages,
        crawl_delay_seconds=ns.crawl_delay,
        obey_robots=not ns.no_robots,
        include_subdomains=not ns.no_subdomains,
        max_linked_files=ns.max_linked_files,
        max_downloaded_images=ns.max_downloaded_images,
        convert_downloaded_assets=not ns.no_convert_downloaded_assets,
        convert_downloaded_images=not ns.no_convert_downloaded_images,
        convert_downloaded_image_to_md_engines=str(ns.convert_downloaded_image_to_md_engines).strip()
        or DEFAULT_IMAGE_TO_MD_ENGINES,
        convert_downloaded_image_to_md_strategy=str(ns.convert_downloaded_image_to_md_strategy),
        convert_downloaded_image_to_md_title=str(ns.convert_downloaded_image_to_md_title or "").strip(),
        post_convert_pdf_ocr=ns.post_convert_pdf_ocr,
        post_convert_ppt_embedded_deep=not ns.no_post_convert_ppt_embedded,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    opts = _options_from_args(ns)

    if ns.urls_file:
        if not ns.urls_file.is_file():
            print(f"URLs file not found: {ns.urls_file}", file=sys.stderr)
            return 2
        raw_lines = ns.urls_file.read_text(encoding="utf-8").splitlines()
        urls = [ln.strip() for ln in raw_lines if ln.strip() and not ln.strip().startswith("#")]
        for u in urls:
            if not _is_http_url(u):
                print(f"Invalid URL (need http/https): {u!r}", file=sys.stderr)
                return 2
        out = ns.output_dir or ns.output
        if not out:
            print("Bulk mode requires -o/--output-dir (or output path as second positional).", file=sys.stderr)
            return 2
        if not opts.artifact_layout:
            opts = opts.with_overrides(artifact_layout=True)
        if opts.crawl:
            print("--crawl is not supported with --urls-file", file=sys.stderr)
            return 2
        out.mkdir(parents=True, exist_ok=True)
        try:
            convert_urls_from_list(urls, out, opts)
        except Exception as e:
            print(f"Conversion failed: {e}", file=sys.stderr)
            if opts.verbose:
                raise
            return 1
        return 0

    if not ns.url or not ns.output:
        parser.error("Provide URL and output path, or use --urls-file with output directory")
    if not _is_http_url(ns.url):
        print("Input must be an http(s) URL", file=sys.stderr)
        return 2
    if opts.crawl and not opts.artifact_layout:
        print("--crawl requires --artifact-layout", file=sys.stderr)
        return 2
    if opts.async_crawl and not opts.crawl:
        print("--async-crawl requires --crawl", file=sys.stderr)
        return 2

    try:
        convert_url(ns.url.strip(), ns.output, opts)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        if opts.verbose:
            raise
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
