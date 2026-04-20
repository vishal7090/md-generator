from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from md_generator.playwright.options import PlaywrightOptions, WaitUntil
from md_generator.playwright.pipeline import convert_url_to_md


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Render SPA pages with Playwright and convert to LLM-ready Markdown.",
    )
    p.add_argument("url", help="HTTP or HTTPS URL to fetch")
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("."),
        help="Output directory (default: current directory)",
    )
    p.add_argument(
        "--wait",
        type=str,
        default=None,
        metavar="SELECTOR",
        dest="wait_selector",
        help="Optional CSS selector to wait for before scrolling",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Navigation timeout in seconds (default: 60)",
    )
    p.add_argument("--user-agent", type=str, default=None, help="Override browser User-Agent")
    p.add_argument(
        "--wait-until",
        type=str,
        choices=("load", "domcontentloaded", "commit", "networkidle"),
        default="networkidle",
        help="Playwright goto wait_until (default: networkidle)",
    )
    p.add_argument(
        "--max-scroll-rounds",
        type=int,
        default=12,
        help="Max scroll-to-bottom iterations for lazy loading (default: 12)",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max fetch attempts with backoff (default: 3)",
    )
    p.add_argument(
        "--no-chunk",
        action="store_true",
        help="Disable chunk markers in output Markdown",
    )
    p.add_argument(
        "--no-readability",
        action="store_true",
        help="Skip readability pass before markdownify",
    )
    p.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Save full-page PNG screenshot to this path",
    )
    p.add_argument(
        "--save-raw-html",
        type=Path,
        default=None,
        help="Save raw rendered HTML to this path",
    )
    p.add_argument(
        "--max-chunk-tokens",
        type=int,
        default=900,
        help="Approximate max tokens per chunk (default: 900)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    u = ns.url.strip()
    if not u.startswith(("http://", "https://")):
        print("URL must start with http:// or https://", file=sys.stderr)
        return 2

    wait_until: WaitUntil = ns.wait_until  # type: ignore[assignment]
    opts = PlaywrightOptions(
        navigation_timeout_ms=ns.timeout * 1000.0,
        wait_selector=ns.wait_selector,
        wait_until=wait_until,
        max_scroll_rounds=ns.max_scroll_rounds,
        max_retries=ns.retries,
        user_agent=ns.user_agent or PlaywrightOptions().user_agent,
        chunk_markdown=not ns.no_chunk,
        max_chunk_tokens=ns.max_chunk_tokens,
        use_readability=not ns.no_readability,
        verbose=ns.verbose,
        screenshot_path=ns.screenshot,
        save_raw_html_path=ns.save_raw_html,
    )

    try:
        path = asyncio.run(convert_url_to_md(u, ns.output, opts))
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        if ns.verbose:
            raise
        return 1

    if ns.verbose:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
