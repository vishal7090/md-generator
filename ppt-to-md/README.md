# ppt-to-md

Convert Microsoft PowerPoint (`.pptx`) to Markdown with extracted images.

## Setup

```bash
cd ppt-to-md
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

For the **HTTP API** (FastAPI + ZIP download + MCP on the same port), also install:

```bash
pip install -r requirements-api.txt
```

## HTTP API (FastAPI, Python 3.11)

Upload a `.pptx`, receive **`artifact.zip`** containing `document.md` and `assets/` (same layout as `--artifact-layout`).

**Run locally** (from `ppt-to-md`, with `PYTHONPATH` = project root — the `pytest` `pythonpath = .` does this automatically):

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

One process serves **REST + Swagger** and **Streamable HTTP MCP** mounted at **`/mcp`** (same host/port). Point MCP clients at e.g. `http://127.0.0.1:8000/mcp`. Optional `FASTMCP_*` env vars still apply to the MCP sub-app where relevant.

- **OpenAPI / Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **`POST /convert/sync`** — multipart field `file` (`.pptx`). Returns `application/zip` immediately if the upload is within **sync** size limits; otherwise **409** with a hint to use jobs.
- **`POST /convert/jobs`** — same upload; returns `{ "job_id", "status" }`. Conversion runs in a background thread.
- **`GET /convert/jobs/{id}`** — `{ "status": "queued"|"running"|"done"|"failed", "error", "created_at" }`
- **`GET /convert/jobs/{id}/download`** — ZIP when `done`; removes the job workspace after the response is sent (one download per job).

**Conversion flags** match the CLI defaults and are passed as **query parameters** on both `sync` and `jobs` (e.g. `extract_embedded_deep=false`, `max_unpack_depth=2`, `emit_extracted_txt_md=true`, `extracted_pdf_ocr=true`). See `/docs` for the full list.

**Environment variables** (all prefixed with `PPT_TO_MD_`):

| Name | Default | Meaning |
|------|---------|---------|
| `PPT_TO_MD_MAX_UPLOAD_MB` | 200 | Hard cap while streaming the upload (**413** if exceeded) |
| `PPT_TO_MD_MAX_SYNC_UPLOAD_MB` | 40 | Sync endpoint only; larger uploads → **409** → use `/convert/jobs` |
| `PPT_TO_MD_JOB_TTL_SECONDS` | 3600 | Completed/failed job dirs removed by a periodic sweeper |
| `PPT_TO_MD_TEMP_DIR` | (empty) | Optional base directory for temp workspaces |
| `PPT_TO_MD_CORS_ORIGINS` | `*` | Comma-separated origins, or `*` |

**Docker** (build from `ppt-to-md`):

```bash
docker build -f Dockerfile.api -t ppt-to-md-api .
docker run --rm -p 8000:8000 ppt-to-md-api
```

### MCP

- **With uvicorn (recommended):** `requirements-api.txt` includes the `mcp` package; Streamable HTTP is already mounted at **`/mcp`** — no second server or port.
- **Standalone** (stdio for Cursor/Claude Desktop, or MCP on its own port): use the same `mcp` dependency and run:

```bash
pip install -r requirements.txt -r requirements-api.txt
python -m api.mcp_server                    # stdio (default)
python -m api.mcp_server --transport sse
python -m api.mcp_server --transport streamable-http   # separate process; set FASTMCP_PORT if 8000 is taken
```

Tools:

- **`convert_pptx_to_artifact_zip(pptx_path)`** — local `.pptx` path on the server → temp `artifact.zip` path.
- **`convert_pptx_base64_to_artifact_zip(pptx_base64, filename="upload.pptx")`** — deck as standard base64 (optional `data:...;base64,` prefix) for cloud/remote clients; max decoded size = **`PPT_TO_MD_MAX_UPLOAD_MB`** (default 200). Returns server path to `artifact.zip` (same as the path tool).

Minimal MCP-only installs can still use `requirements-mcp.txt` instead of the full API file list.

#### MCP Inspector notes

- **`MCP_PROXY_AUTH_TOKEN` in the URL** (e.g. `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...`) is **only for the Inspector web UI ↔ Inspector’s own proxy**. It is **not** a token your `ppt-to-md` server validates; our endpoint has **no** auth.
- Prefer **Direct** transport to **`http://localhost:8000/mcp`** (or `127.0.0.1`) while `uvicorn` is running. **Via Proxy** can hit [known session / Streamable HTTP issues](https://github.com/modelcontextprotocol/inspector/issues/492) in some Inspector versions.
- If connection still fails after a server restart, ensure you pulled a build that runs **Streamable HTTP session lifespan** with FastAPI (mounted MCP sub-apps do not run Starlette lifespan by default).

## Usage

From the `ppt-to-md` directory:

```bash
python converter.py path/to/input.pptx path/to/output.md
```

Or:

```bash
python -m src.converter path/to/input.pptx path/to/output.md
```

### Artifact bundle (matches `ppt-artifact-to-markdown-generator.prompt.md`)

Write `document.md` plus `assets/images`, `assets/charts`, `assets/tables`, `assets/media`, and `assets/other` under an **output directory**:

```bash
python -m src.converter path/to/input.pptx path/to/output_dir --artifact-layout -v
```

- Slide headings use `## Slide {n}: {title}` in `document.md`.
- Images: `assets/images/slide_{n}_img_{i}.{ext}`.
- Tables: GFM in Markdown; optional CSV under `assets/tables/slide_{n}_table_{i}.csv` (default on; use `--no-table-csv` to disable).
- Media: slide-linked files under `assets/media/`; remaining `ppt/media` members are copied as `orphan_*` and listed under “Extracted package media (unreferenced)”.
- Charts: chart CSV and chart image placeholders under `assets/charts/slide_{n}_chart_{i}.{csv|png}`.
- Embedded package objects: deep extraction into `assets/other/embedded/` with recursive unzip and manifest. OLE “package” blobs also read the `Ole10Native` stream (via `olefile`) and write the original file under `slide_*_obj_*_payload/` when possible. If that extracted file is itself a ZIP, it is unpacked under `slide_*_obj_*_native_payload_unpacked/` (same `max-unpack-depth` as other zips). If structured extraction fails and there is no ZIP payload inside the OLE blob, the tool scans OLE streams for decodable text and may write `slide_*_obj_*_ole_stream_text.txt`; each embedding records `ole_extraction.status` (`ole10native`, `zip_in_ole`, `stream_text_fallback`, or `failed`) in `assets/extraction_manifest.json`.
- Extraction manifest: `assets/extraction_manifest.json`.
- After conversion, every `.txt` file under `assets/` (except `assets/extracted_md/`) is copied into a companion Markdown file under `assets/extracted_md/`, and a **Extracted text from package assets** section is appended to `document.md` (inline body for files up to ~48k characters, otherwise link-only). Disable with `--no-extracted-txt-md`.
- Every `.docx` and `.pdf` under `assets/` (same exclusions) is converted using vendored stacks aligned with the sibling **word-to-md** (Mammoth → markdownify) and **pdf-to-md** (PyMuPDF + pdfplumber) projects under `src/vendor_word_md/` and `src/vendor_pdf_md/`. Outputs: `assets/extracted_md/*.md` plus images in `assets/extracted_md_media/<NNNN_slug>/`. A **Extracted Word and PDF (Markdown)** section is appended to `document.md`. Flags: `--no-extracted-docx-md`, `--no-extracted-pdf-md`. Optional sparse-page OCR: `--extracted-pdf-ocr` and `--extracted-pdf-ocr-min-chars N` (requires [Tesseract](https://github.com/tesseract-ocr/tesseract) installed and `pytesseract` + Pillow in `requirements.txt`). Legacy `.doc` is not supported.
- Every `.xlsx` and `.xlsm` under `assets/` (same exclusions) is converted with **openpyxl** to GFM tables per worksheet; standalone files under `assets/extracted_md/` and a **Extracted Excel (Markdown)** section in `document.md` (same ~48k inline cap as other merges). Disable with `--no-extracted-xlsx-md`. Legacy `.xls` is not supported.
- **Maintenance:** If you change `word-to-md` or `pdf-to-md` upstream, refresh the copies under `src/vendor_word_md/` and `src/vendor_pdf_md/` accordingly.
- `--images-dir` is **ignored** when `--artifact-layout` is set (paths are fixed under `assets/`).
- Depth and toggles:
  - `--max-unpack-depth N`
  - `--no-chart-data`
  - `--no-chart-image`
  - `--extract-embedded-deep` / `--no-extract-embedded-deep`

### Classic single-file output

Options:

- `--images-dir DIR` — store images under `DIR` (default: `<parent of output.md>/images`)
- `--no-title-slide-h1` — use `##` for all slide titles (default: first slide title uses `#`)
- `--no-strip-known-footers` — do not remove lines matching built-in patterns (e.g. standalone “Confidential”)
- `-v` / `--verbose` — print extraction warnings to stderr

### Feature 2551511 (artifact layout)

From `ppt-to-md`, with the deck under `doc/`:

```bash
python -m src.converter "../doc/Feature 2551511 - DOT_Aadhar Based Retailer Onboarding_Modification - Partner Onboard.pptx" "../.cursor/artifacts/2551511/ppt_artifact" --artifact-layout -v
```

This produces `../.cursor/artifacts/2551511/ppt_artifact/document.md` and the `assets/` tree.

**Classic** single-file output (no bundle):

```bash
python -m src.converter "../doc/Feature 2551511 - DOT_Aadhar Based Retailer Onboarding_Modification - Partner Onboard.pptx" "../.cursor/artifacts/2551511/Partner_Onboard.md" -v
```

## Pipeline

1. **python-pptx** — read slides, text frames (bullets and numbered lists where OOXML exposes them), tables, pictures, charts, speaker notes.
2. **OOXML zip** — optional copy of `ppt/media` and slide-linked relationships for artifact mode.
3. **Markdown** — headings per slide, GFM tables, blockquoted notes (`> Notes:`), chart placeholders (`- Chart: …` or `<!-- Chart: title not available -->`).

## Limitations

- **Charts:** Numeric series and “insights” are not parsed; the tool does not render charts as PNG without external tools.
- **Complex layouts:** Floating text boxes, SmartArt, and merged cells may need manual cleanup.
- **Footers:** Built-in stripping targets common footer-only lines (e.g. “Confidential”); deck-specific footers may need `--no-strip-known-footers` plus manual edits.

## Tests

Regenerate the minimal fixture if needed:

```bash
python tests/build_fixture.py
```

Run tests:

```bash
pytest tests/ -v
```
