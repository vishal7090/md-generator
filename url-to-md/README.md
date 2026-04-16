# url-to-md

Convert public **HTTP/HTTPS** HTML pages to Markdown with downloaded images and linked files (optional), plus optional same-site crawl.

Server-rendered HTML only: there is no headless browser; heavy client-side SPAs may not convert fully until a future Playwright-based pass.

## Setup

From the repository root (so `md_generator` is importable):

```bash
cd url-to-md
python -m venv .venv
.venv\Scripts\activate
pip install -e "..[url]"
```

To **post-convert** downloaded files (PDF, DOCX, PPTX, XLSX/CSV, ZIP, TXT/JSON/XML) into `assets/extracted_md/` using the same engines as the other `md-*` tools, install the convenience extra:

```bash
pip install -e "..[url-full]"
```

(`url-full` includes PDF, Word, PPTX, XLSX, archive, and OCR-related deps used by those converters; optional `image` / `image-ocr` is only needed for `--convert-downloaded-images`.)

For the **HTTP API** (FastAPI + ZIP download + MCP on the same port):

```bash
pip install -e "..[url,api,mcp]"
# or with post-convert deps:
pip install -e "..[url-full,api,mcp]"
```

## HTTP API (FastAPI)

Run locally:

```bash
uvicorn md_generator.url.api.main:app --reload --host 127.0.0.1 --port 8011
```

- **OpenAPI / Swagger UI:** [http://127.0.0.1:8011/docs](http://127.0.0.1:8011/docs)
- **`POST /convert/sync`** — JSON body with `url` **or** `urls` (list). Returns `application/zip` containing `document.md` and `assets/` (and `pages/` when crawling or bulk). If there are too many URLs or `crawl` + `max_pages` exceeds sync limits, returns **409** with a hint to use jobs.
- **`POST /convert/jobs`** — same JSON body; returns `{ "job_id", "status" }`.
- **`GET /convert/jobs/{id}`** — `{ "status": "queued"|"running"|"done"|"failed", "error", "created_at" }`
- **`GET /convert/jobs/{id}/download`** — ZIP when `done`; removes the job workspace after the response is sent.

**JSON body fields** (subset): `url`, `urls`, `crawl`, `max_depth`, `max_pages`, `crawl_delay_seconds`, `obey_robots`, `include_subdomains`, `table_csv`, `download_linked_files`, `timeout_seconds`, `max_response_mb`, `convert_downloaded_assets`, `convert_downloaded_images`, `post_convert_pdf_ocr`, `post_convert_pdf_ocr_min_chars`, `post_convert_ppt_embedded_deep`, `max_linked_files`, `max_downloaded_images`. Query parameters with the same names override the body where supported (see `/docs`).

**Environment variables** (prefix `URL_TO_MD_`):

| Name | Default | Meaning |
|------|---------|---------|
| `URL_TO_MD_MAX_SYNC_URLS` | 3 | Max URLs in one sync request |
| `URL_TO_MD_MAX_SYNC_CRAWL_PAGES` | 8 | If `crawl` is true, `max_pages` above this forces **409** → jobs |
| `URL_TO_MD_MAX_JOB_URLS` | 50 | Max URLs per request (sync or jobs) |
| `URL_TO_MD_JOB_TTL_SECONDS` | 3600 | Completed/failed job dirs removed by sweeper |
| `URL_TO_MD_TEMP_DIR` | (empty) | Optional base directory for job workspaces |
| `URL_TO_MD_CORS_ORIGINS` | `*` | Comma-separated origins, or `*` |

### MCP

Mounted at **`/mcp`** on the same server as the API. Standalone:

```bash
python -m md_generator.url.api.mcp_server
python -m md_generator.url.api.mcp_server --transport streamable-http
```

Tool: **`convert_url_to_artifact_zip(url, crawl=False, ...)`** — returns a server temp path to `artifact.zip`.

### Docker

Build from the **repository root**:

```bash
docker build -f url-to-md/Dockerfile.api -t url-to-md-api .
docker run --rm -p 8011:8000 url-to-md-api
```

## CLI

From `url-to-md` (or use `md-url` after `pip install -e "..[url]"`):

```bash
python converter.py https://example.com/article ./out --artifact-layout
```

- **Artifact layout:** `out/document.md`, `out/assets/images/`, `out/assets/files/`, optional `out/assets/tables/*.csv`, `out/assets/crawl_manifest.json`.
- **Classic:** `python converter.py https://example.com/page ./page.md` — images under `./images/` (or `--images-dir`).
- **Bulk:** `python converter.py --urls-file urls.txt -o ./bulk_out` (forces artifact layout; one subdirectory per URL + root `document.md` index).
- **Crawl:** `python converter.py https://example.com/ ./crawl --artifact-layout --crawl --max-depth 2 --max-pages 30` — root index + `pages/<slug>/document.md` per page.
- **Post-convert linked files:** by default, each page run converts files under `assets/files/` (PDF, DOCX, PPTX, XLSX/CSV, ZIP, TXT/JSON/XML) into `assets/extracted_md/` and appends a section to `document.md`. Disable with `--no-convert-downloaded-assets`. Optional `--convert-downloaded-images` runs OCR on downloaded rasters in `assets/images/` (needs `mdengine[image]` and Tesseract). Tuning: `--max-linked-files`, `--max-downloaded-images`, `--post-convert-pdf-ocr`, `--no-post-convert-ppt-embedded`.

Respect site terms, rate limits, and `robots.txt`. Defaults include a crawl delay and `robots.txt` checks (`--no-robots` to disable).

## Tests

```bash
cd ..
pytest url-to-md/tests -v
```

## Pipeline

1. **httpx** — fetch HTML with size limit and timeout.
2. **readability-lxml** — main article HTML; **markdownify** — Markdown body.
3. **BeautifulSoup** — discover images and whitelisted file links; download under `assets/` (or `images/` in classic mode).
4. Optional **CSV** sidecars for `<table>` elements in the full HTML.
5. **Post-convert** — each file in `assets/files/` with a known extension is passed to the matching in-repo converter; outputs live under `assets/extracted_md/` (and `assets/extracted_md_media/` for Word images). A JSON log is written to `assets/asset_convert_log.json`.

## Limitations

- No JavaScript execution; dynamic-only sites need a different tool chain.
- Crawl scope is same-site (scheme + host, optional subdomains via `--no-subdomains` / API `include_subdomains`).
- Binary non-HTML responses are rejected with a clear error.
