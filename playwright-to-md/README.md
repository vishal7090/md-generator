# playwright-to-md (md-playwright)

Render JavaScript-heavy pages (React, Angular, SPAs) with [Playwright](https://playwright.dev/python/), extract readable content, convert to Markdown, optionally download images, and emit chunk markers for LLM workflows.

## Install

```bash
pip install "mdengine[playwright]"
playwright install chromium
```

The second line downloads the Chromium browser binaries required at runtime.

## CLI

```bash
md-playwright https://react.dev/learn/tutorial-tic-tac-toe -o ./out --wait ".markdown"
```

Common flags:

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output directory (writes `document.md`) |
| `--wait` | CSS selector to wait for before scrolling |
| `--timeout` | Navigation timeout in seconds (default: 60) |
| `--wait-until` | `load`, `domcontentloaded`, `commit`, or `networkidle` (default: `networkidle`) |
| `--max-scroll-rounds` | Scroll passes for lazy-loaded content |
| `--no-chunk` | Disable `<!-- chunk:start -->` markers |
| `--no-readability` | Skip readability extraction before markdownify |
| `--screenshot` | Save full-page PNG path |
| `--save-raw-html` | Save rendered HTML path |
| `--retries` | Retry count for navigation failures |

## Library

```python
import asyncio
from pathlib import Path
from md_generator.playwright import PlaywrightOptions, convert_url_to_md

async def run():
    await convert_url_to_md(
        "https://angular.dev/overview",
        Path("out"),
        PlaywrightOptions(chunk_markdown=True),
    )

asyncio.run(run())
```

## HTTP API (sync ZIP, async jobs, MCP)

Install **`mdengine[playwright,api,mcp]`** (and `playwright install chromium`). Same route shape as **url-to-md**: JSON body with **`url`** or **`urls`**, optional Playwright fields (`navigation_timeout_seconds`, `wait_selector`, `wait_until`, `max_scroll_rounds`, …).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/convert/sync` | Returns `application/zip` immediately (up to `PLAYWRIGHT_TO_MD_MAX_SYNC_URLS` targets). |
| `POST` | `/convert/jobs` | Queues conversion; returns `{ "job_id", "status" }`. |
| `GET` | `/convert/jobs/{job_id}` | Job status and error text. |
| `GET` | `/convert/jobs/{job_id}/download` | ZIP when `status` is `done`. |

FastMCP is mounted at **`/mcp`** (streamable HTTP on the same port as Uvicorn). Standalone MCP supports **stdio** (default), **sse**, and **streamable-http**:

```bash
md-playwright-api --host 127.0.0.1 --port 8014
# or: uvicorn md_generator.playwright.api.main:app --host 127.0.0.1 --port 8014

md-playwright-mcp --transport stdio
python -m md_generator.playwright.api.mcp_server --transport sse
python -m md_generator.playwright.api.mcp_server --transport streamable-http
```

Environment prefix: **`PLAYWRIGHT_TO_MD_`** (for example `PLAYWRIGHT_TO_MD_MAX_SYNC_URLS`, `PLAYWRIGHT_TO_MD_MAX_JOB_URLS`, `PLAYWRIGHT_TO_MD_JOB_TTL_SECONDS`, `PLAYWRIGHT_TO_MD_TEMP_DIR`, `PLAYWRIGHT_TO_MD_CORS_ORIGINS`, `PLAYWRIGHT_TO_MD_API_HOST`, `PLAYWRIGHT_TO_MD_API_PORT`). See `md_generator.playwright.api.settings`.

## Notes

- `networkidle` can be flaky on long-polling SPAs; use `--wait-until load` if needed.
- Chunking uses a **character-based** token estimate (~4 characters per token), not a tokenizer.
- Integration tests hit the public web; mark with `@pytest.mark.integration` and install browsers to run them.
