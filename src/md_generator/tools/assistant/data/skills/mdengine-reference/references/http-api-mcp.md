# HTTP API (FastAPI) and MCP — consumer reference

Condensed from the upstream **`mdengine` README** (same version you install from PyPI). When in doubt, verify against the README shipped with your installed package or the repository.

---

## Common job pattern (most format HTTP APIs)

- **`POST /convert/sync`** — upload a file (multipart field **`file`**) **or** JSON for URL-style services; response may be Markdown or a **ZIP** bundle.
- **`POST /convert/jobs`** — async job; returns `job_id`.
- **`GET /convert/jobs/{job_id}`** — status.
- **`GET /convert/jobs/{job_id}/download`** — result when ready.

**URL** conversion uses a **JSON** body (`url` or `urls`); see **url-to-md** README for fields.

---

## Uvicorn targets (FastAPI `app`)

Install **`mdengine[api]`** plus the format extra(s), then run the **`app`** (or `create_app` with **`--factory`** for media) from:

| Service | Uvicorn target | Required extras (typical) |
|---------|----------------|---------------------------|
| PDF | `md_generator.pdf.api.main:app` | `pdf`, `api` |
| Word | `md_generator.word.api.main:app` | `word`, `api`, `mcp` (Word mounts FastMCP) |
| PPTX | `md_generator.ppt.api.main:app` | `ppt`, `api`, `mcp` |
| XLSX | `md_generator.xlsx.api.app:app` | `xlsx`, `api` |
| Image | `md_generator.image.api.main:app` | `image`, `api`, `mcp` |
| Text/JSON/XML | `md_generator.text.api.main:app` | `text`, `api`, `mcp` |
| ZIP | `md_generator.archive.api.main:app` | `archive`, `api`, `mcp` (+ extras for nested office/PDF) |
| URL / HTML | `md_generator.url.api.main:app` | `url`, `api`, `mcp` |
| Playwright / SPA | `md_generator.playwright.api.main:app` | `playwright`, `api`, `mcp` |
| Database metadata | `md_generator.db.api.main:app` | `db`, `api`, `mcp` |
| Graph metadata (Neo4j / NetworkX) | `md_generator.graph.api.main:app` | `graph`, `api`, `mcp` |
| OpenAPI → Markdown | `md_generator.openapi.api.main:app` | `openapi`, `api`, `mcp` |
| Audio (Whisper) | `md_generator.media.audio.api.main:create_app` (**`--factory`**) or `…main:app` | `audio`, `api`, `mcp` |
| Video (Whisper) | `md_generator.media.video.api.main:create_app` (**`--factory`**) or `…main:app` | `video`, `api`, `mcp` |
| YouTube | `md_generator.media.youtube.api.main:create_app` (**`--factory`**) or `…main:app` | `youtube`, `api`, `mcp` |

**Port note:** **`md-graph-api`** and **`md-video-api`** both default to **8012**; set **`GRAPH_TO_MD_PORT`** or **`MD_VIDEO_API_PORT`** when both run on one machine. **`md-openapi-api`** defaults to **8015** (`OPENAPI_TO_MD_PORT`) to avoid **`md-youtube-api`** (**8013**) and **`md-playwright-api`** (**8014**).

---

## MCP over HTTP (same host as REST)

Apps mount MCP at **`/mcp`** (Streamable HTTP / framework-specific). Example: `http://127.0.0.1:<port>/mcp`.

---

## `md-db-api` routes (from README command table)

FastAPI on port **8010** (`DB_TO_MD_PORT`):

- `POST /db-to-md/run`
- `POST /db-to-md/run/sqlite` (upload + ZIP)
- `POST /db-to-md/job`
- `POST /db-to-md/job/sqlite` (upload + async job)
- SSE `/db-to-md/job/{id}/events`

**SQLite upload:** `POST /db-to-md/run/sqlite` — `multipart/form-data` field **`file`** (`.sqlite` / `.db`, SQLite header); optional **`config`** (JSON string). `POST /db-to-md/job/sqlite` — same; `GET /db-to-md/job/{id}/download` when complete. Caps: **`DB_TO_MD_MAX_SQLITE_UPLOAD_MB`** (default **256**), **`DB_TO_MD_MAX_SYNC_ZIP_MB`** on sync route.

---

## `md-graph-api` routes

Port **8012** (`GRAPH_TO_MD_PORT`): `POST /graph-to-md/run`, `/graph-to-md/job`, SSE `/graph-to-md/job/{id}/events`.

---

## `md-openapi-api`

Port **8015** (`OPENAPI_TO_MD_PORT`): `POST /openapi-to-md/generate` (OpenAPI upload → ZIP), `/health`, MCP at **`/mcp`**.

**Standalone `md-openapi-mcp` tools:** `api_validate_openapi_yaml`, `api_generate_readme_markdown`, `api_run_sync_zip_base64`.

---

## Media REST (audio / video / YouTube)

| Endpoint | Description |
|----------|-------------|
| `POST /convert/sync` | Multipart **`file`** → Markdown (audio/video). Query: `whisper_model`, `language`, `title`. |
| `POST /convert/jobs` | Async upload → `{ job_id, status }`. |
| `GET /convert/jobs/{job_id}` | Status JSON. |
| `GET /convert/jobs/{job_id}/download` | Markdown when `done`. |

**YouTube** uses **JSON** (not multipart) on `POST /convert/sync` and `POST /convert/jobs`: `url`, `title`, `transcript_languages`, `enable_audio_fallback`, `whisper_model`, `language`, etc.

**Defaults:** `MD_AUDIO_API_PORT=8011`, `MD_VIDEO_API_PORT=8012`, `MD_YOUTUBE_API_PORT=8013` (plus `MD_*` limits and temp dirs — see README).

**Bundled runners:**

```bash
md-audio-api --host 127.0.0.1 --port 8011
md-video-api --host 127.0.0.1 --port 8012
md-youtube-api --host 127.0.0.1 --port 8013
```

Swagger: **`/docs`** when running.

---

## Media MCP

1. **With FastAPI** — MCP at **`http://<host>:<port>/mcp`** on the same server as `md-*-api`.
2. **Standalone:** `md-audio-mcp`, `md-video-mcp`, `md-youtube-mcp` with `--transport stdio|sse|streamable-http`.

**Tools (names from README):**

- Audio: `transcribe_audio_path`, `transcribe_audio_base64`
- Video: `transcribe_video_path`, `transcribe_video_base64`
- YouTube: `youtube_url_to_markdown`

---

## Standalone MCP processes (other formats)

| Converter | Command (examples) |
|-----------|---------------------|
| ZIP | `python -m md_generator.archive.api.mcp_server` / `--transport sse` / `streamable-http` |
| Text/JSON/XML | `python -m md_generator.text.api.mcp_server` |
| Word | `python -m md_generator.word.api.mcp_server` / `--transport stdio` / `streamable-http` + `--host` / `--port` |
| PDF | `python -m md_generator.pdf.api.mcp_server` / `--transport stdio` / `sse` / `streamable-http` |
| PPTX | `python -m md_generator.ppt.api.mcp_server` |
| Image | `python -m md_generator.image.api.mcp_server` |
| URL / HTML | `python -m md_generator.url.api.mcp_server` / `--transport sse` / `streamable-http` |
| Playwright | `md-playwright-mcp` or `python -m md_generator.playwright.api.mcp_server` |
| Audio / Video / YouTube | `md-*-mcp` or `python -m md_generator.media.*.api.mcp_server` |
| Database | `md-db-mcp` or `python -m md_generator.db.api.mcp_server` |
| Graph | `md-graph-mcp` or `python -m md_generator.graph.api.mcp_server` |
| OpenAPI | `md-openapi-mcp` or `python -m md_generator.openapi.api.mcp_server` |

Install **`mdengine[mcp]`** (and usually **`[api]`** for HTTP) so MCP imports resolve.

---

## Environment variable prefixes (limits & CORS)

| Service | Prefix | Examples |
|---------|--------|----------|
| PDF | `PDF_TO_MD_` | `PDF_TO_MD_MAX_UPLOAD_MB`, `PDF_TO_MD_MAX_SYNC_UPLOAD_MB`, `PDF_TO_MD_TEMP_DIR`, `PDF_TO_MD_CORS_ORIGINS` |
| Word | `WORD_TO_MD_` | `WORD_TO_MD_MAX_UPLOAD_MB`, … |
| ZIP | `ZIP_TO_MD_` | … |
| PPTX | `PPT_TO_MD_` | … |
| Text | `TXT_JSON_XML_TO_MD_` | … |
| XLSX | `XLSX_TO_MD_` | … |
| URL | `URL_TO_MD_` | `URL_TO_MD_MAX_SYNC_URLS`, … |
| Playwright | `PLAYWRIGHT_TO_MD_` | … default API port **8014** |
| Database | `DB_TO_MD_` | default **8010** |
| Graph | `GRAPH_TO_MD_` | default **8012** |
| OpenAPI | `OPENAPI_TO_MD_` | default **8015** |
| Audio | `MD_AUDIO_` | … port **8011** |
| Video | `MD_VIDEO_` | … port **8012** |
| YouTube | `MD_YOUTUBE_` | … port **8013** |

Exact names live in each package’s `api/settings` or `api/app` module.
