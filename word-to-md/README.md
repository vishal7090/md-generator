# word-to-md Convert Microsoft Word (.docx) to Markdown with extracted images. ## Setup
bash
cd word-to-md
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
For the **HTTP API** (FastAPI, OpenAPI/Swagger, ZIP download, Streamable MCP on /mcp):
bash
pip install -r requirements.txt -r requirements-api.txt
## Usage ### 1) CLI (file → Markdown path) From the word-to-md directory:
bash
python converter.py path/to/input.docx path/to/output.md
Or:
bash
python -m src.converter path/to/input.docx path/to/output.md
Or unified runner:
bash
python run.py cli -- input.docx output.md -v
### 2) HTTP API (file upload → ZIP bundle) Start the server (Swagger UI at /docs, ReDoc at /redoc):
bash
python run.py api --host 127.0.0.1 --port 8002
# or: uvicorn api.main:app --host 127.0.0.1 --port 8002
- **POST /convert/sync** — multipart field file (.docx). Response: artifact.zip containing document.md, images/, and conversion_log.txt. For files larger than WORD_TO_MD_MAX_SYNC_UPLOAD_MB (default 40), use jobs. - **POST /convert/jobs** — same upload; returns { "job_id", "status" }. Poll **GET /convert/jobs/{id}**, then **GET /convert/jobs/{id}/download** for the ZIP. Query params (both routes): page_break_as_hr (bool, default true). Environment (prefix WORD_TO_MD_): MAX_UPLOAD_MB, MAX_SYNC_UPLOAD_MB, JOB_TTL_SECONDS, TEMP_DIR, CORS_ORIGINS. ### 3) FastMCP (Streamable HTTP on same port as API) With run.py api or uvicorn api.main:app, MCP is mounted at **/mcp** (Streamable HTTP). Standalone MCP process:
bash
python run.py mcp --transport stdio
python -m api.mcp_server --transport streamable-http
Tools: convert_docx_to_artifact_zip, convert_docx_base64_to_artifact_zip. Options: - --images-dir DIR — store images under DIR (default: <parent of output.md>/images) - --no-page-break-hr — disable heuristic that maps some page-break-like spans to --- - -v / --verbose — print Mammoth conversion messages to stderr Example for a project document:
bash
python converter.py ../doc/Reliance_Aviation_AI_Plan.docx output/Reliance_Aviation_AI_Plan.md
## Pipeline 1. **Mammoth** — DOCX → HTML (style map for Heading 1–6 and common styles). 2. **Image handler** — writes embedded images next to the Markdown (default images/). 3. **markdownify** — HTML → ATX Markdown (headings, lists, tables, links, emphasis). Complex Word features (merged table cells, floating text boxes) may need manual cleanup after conversion. ## Tests
bash
pip install -r requirements.txt -r requirements-api.txt
pytest tests/ -v
Core converter tests run with requirements.txt only; API/MCP tests skip if FastAPI/MCP are missing.