# pdf-to-md Convert PDF files to Markdown with optional image extraction, table detection (pdfplumber), and optional OCR for scanned pages. ## Setup
bash
cd pdf-to-md
python -m pip install -r requirements.txt
### Optional: OCR (scanned PDFs) OCR is **not** installed by default. To use --ocr: 1. Install Python packages: pip install pytesseract Pillow 2. Install **Tesseract OCR** on your system: - **Windows**: Install from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) or your package manager. Add the install folder to PATH, or set TESSDATA_PREFIX if needed. - **macOS**: brew install tesseract - **Linux**: apt install tesseract-ocr (or equivalent) If Tesseract is not on PATH, configure pytesseract.pytesseract.tesseract_cmd (see pytesseract docs). ## Usage
bash
python converter.py input.pdf output.md
- Images are written next to the Markdown file under images/ by default (or use --images-dir). - Each page is introduced with ## Page N for traceability. **Artifact bundle (same layout as ppt-to-md ZIP):**
bash
python converter.py input.pdf ./my-bundle --artifact-layout
Writes my-bundle/document.md and my-bundle/assets/images/. ### Options | Flag | Meaning | |------|--------| | --artifact-layout | Write OUTPUT/document.md + OUTPUT/assets/... (for APIs / ZIP) | | --images-dir DIR | Directory for extracted images (ignored with --artifact-layout; default: <output_parent>/images) | | --ocr | Run Tesseract on pages with very little embedded text (see --ocr-min-chars) | | --ocr-min-chars N | Pages with fewer than N characters of plain text are treated as scanned when --ocr is set (default: 40) | | -v, --verbose | Print warnings (e.g. image extraction) to stderr | ### Example (Digital Locker spec)
bash
python converter.py "../doc/Digital Locker Authorized Partner API Specification v1.11.pdf" "../.cursor/artifacts/2551511/Digital_Locker_Authorized_Partner_API_Spec_v1.11.md"
Adjust the output path to match your FeatureID / artifact layout. ## HTTP API (FastAPI) + Swagger + ZIP Install API dependencies:
bash
pip install -r requirements.txt -r requirements-api.txt
Run one process (**REST**, **Swagger** at /docs, **OpenAPI** at /openapi.json, **Streamable HTTP MCP** at /mcp):
bash
uvicorn api.main:app --host 127.0.0.1 --port 8001
- **Sync ZIP:** POST /convert/sync — multipart field file (.pdf). Response: artifact.zip containing document.md and assets/. - **Async job:** POST /convert/jobs → GET /convert/jobs/{job_id} → GET /convert/jobs/{job_id}/download when status is done. - **Query params:** ocr, ocr_min_chars (same meaning as CLI). **Limits (environment, prefix PDF_TO_MD_):** MAX_UPLOAD_MB (default 200), MAX_SYNC_UPLOAD_MB (default 40), JOB_TTL_SECONDS, TEMP_DIR, CORS_ORIGINS. Use port **8001** if **8000** is already used by ppt-to-md. ### Standalone MCP (stdio / separate streamable-http)
bash
python -m api.mcp_server
python -m api.mcp_server --transport streamable-http
**MCP tools:** convert_pdf_to_artifact_zip (local path), convert_pdf_base64_to_artifact_zip (base64 body). Prefer connecting MCP clients to **http://127.0.0.1:8001/mcp** while uvicorn is running (same as ppt-to-md pattern). ## Limitations (v1) - **Tables**: pdfplumber-detected tables are appended after the main text of each page; the same content may also appear in the narrative text block. Review and deduplicate if needed. - **Multi-column layouts**: Reading order follows block geometry; complex magazines or newspapers may need manual cleanup. - **Headings**: Heuristic from font size vs. median body size; unusual PDFs may misclassify lines. - **Links**: URI annotations are not expanded to Markdown links in this version. - **Charts**: Raster images are extracted; vector diagrams appear as images when embedded as XObjects. ## Tests tests/conftest.py creates tests/fixtures/minimal.pdf on first run if missing. You can also run python tests/build_fixture.py manually.
bash
python -m pytest tests -v
API/MCP tests require pip install -r requirements-api.txt (they skip if fastapi / mcp is missing). ## Layout - src/pdf_extract.py — PyMuPDF text/images, pdfplumber tables, optional OCR - src/md_emit.py — Markdown table formatting helpers - src/converter.py — CLI - src/utils.py — paths, image filenames, artifact bundle dirs - api/ — FastAPI routes, ZIP bundling, FastMCP tools + /mcp mount