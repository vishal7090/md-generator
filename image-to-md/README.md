# image-to-md

Convert images to Markdown using Tesseract, PaddleOCR, and/or EasyOCR (`--engines`, `--strategy compare|best`).

## Setup

```bash
cd image-to-md
python -m pip install -r requirements.txt
```

Optional OCR backends: `pip install -r requirements-ocr.txt` (large). Tesseract binary must be on `PATH` for `tess`, or set `TESSERACT_CMD` / `IMAGE_TO_MD_TESSERACT_CMD`.

## CLI

```bash
python converter.py path/to/image_or_dir output.md --engines easy --strategy best
python converter.py path/to/dir ./bundle --artifact-layout
```

On Windows, if EasyOCR fails during model download with a `charmap` error, use `python -X utf8 converter.py ...`.

## HTTP API (FastAPI) + MCP

```bash
pip install -r requirements.txt -r requirements-api.txt
uvicorn api.main:app --host 127.0.0.1 --port 8008
```

- **Swagger:** `/docs`, **OpenAPI:** `/openapi.json`, **MCP (Streamable HTTP):** `/mcp`
- **Sync:** `POST /convert/sync` — multipart field `file` (one image or a `.zip` of images). Response: `artifact.zip` with `document.md`.
- **Async:** `POST /convert/jobs` → `GET /convert/jobs/{job_id}` → `GET /convert/jobs/{job_id}/download` when `status` is `done`.

**Query params:** `engines`, `strategy`, `title`, `lang` (Tesseract), `paddle_lang`, `paddle_no_angle_cls`, `easy_lang` (comma-separated for EasyOCR).

**Limits (env prefix `IMAGE_TO_MD_`):** `MAX_UPLOAD_MB` (default 200), `MAX_SYNC_UPLOAD_MB` (default 40), `JOB_TTL_SECONDS`, `TEMP_DIR`, `CORS_ORIGINS`, `TESSERACT_CMD`.

### Standalone MCP

```bash
python -m api.mcp_server
python -m api.mcp_server --transport streamable-http
```

**Tools:** `convert_image_path_to_artifact_zip` (local file, directory, or `.zip`), `convert_image_base64_to_artifact_zip` (base64 image or zip).

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
