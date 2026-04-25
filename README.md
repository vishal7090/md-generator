# mdengine

Single Python distribution for converting **PDF**, **Word (.docx)**, **PowerPoint (.pptx)**, **Excel (.xlsx/.xlsm)**, **images** (OCR), **plain text / JSON / XML**, **ZIP archives**, **audio / video** (Whisper transcription → Markdown), **database metadata** (SQL + Mongo), and **graphs** (Neo4j / NetworkX → Markdown) into **Markdown** (and related assets). Install only the extras you need; everything imports under the **`md_generator`** package.

- **PyPI name:** `mdengine` (import package: `md_generator`)
- **Source:** [github.com/vishal7090/md-generator](https://github.com/vishal7090/md-generator)
- **Python:** 3.10+
- **License:** [MIT](LICENSE)

**Quick links:** [On a new computer](#on-a-new-computer) · [Command-line execution](#command-line-execution) · [Python library](#python-library) · [Audio and video](#audio-and-video-to-markdown) · [HTTP API](#http-api-fastapi) · [MCP](#mcp-model-context-protocol) · [Development](#development) · [Code of Conduct](CODE_OF_CONDUCT.md)

---

## On a new computer

Use this checklist the first time you run the tools on a machine that does not have the project yet.

1. **Install Python 3.10 or newer** from [python.org](https://www.python.org/downloads/) (Windows: enable **Add python.exe to PATH** in the installer). Confirm in a new terminal: `python --version`.
2. **(Recommended)** Create an isolated environment so dependencies do not clash with other projects:
   ```bash
   python -m venv .venv
   ```
   Then activate it: **Windows (PowerShell)** `.\.venv\Scripts\Activate.ps1` · **Windows (CMD)** `.venv\Scripts\activate.bat` · **macOS / Linux** `source .venv/bin/activate`.
3. **Install this package with the extras you need** (see [Optional dependency extras](#optional-dependency-extras) for what each extra does):
   ```bash
   pip install "mdengine[pdf,word]"
   ```
   If the package is not on PyPI yet, clone [the repository](https://github.com/vishal7090/md-generator), `cd` into the repo root, then:
   ```bash
   pip install -e ".[pdf,word]"
   ```
4. **Confirm the CLI is on your PATH:** `md-pdf --help` (or `md-word --help`, etc.). If you see “command not found”, the folder where `pip` puts scripts (often `.venv\Scripts` on Windows or `.venv/bin` on Unix) must be on your `PATH`, or you must run commands from an **activated** virtual environment.
5. **Run one conversion** with a real file path, for example:
   ```bash
   md-pdf path\to\report.pdf out.md
   ```
   Full flags and every `md-*` command are in [Command-line execution](#command-line-execution).

---

## Installation

From the repository root (editable install for development):

```bash
pip install -e .
```

With format-specific and HTTP extras:

```bash
pip install -e ".[pdf,word,api]"
pip install -e ".[ppt,xlsx,image,archive,api,mcp]"
```

From PyPI (once published):

```bash
pip install "mdengine[pdf,word]"
pip install "mdengine[all]"
```

### Optional dependency extras

| Extra | Purpose |
|--------|---------|
| `pdf` | PDF extraction (PyMuPDF, pdfplumber) |
| `word` | DOCX → Markdown (mammoth, markdownify) |
| `ppt` | PPTX and embedded content (python-pptx, Pillow, lxml, mammoth, PyMuPDF, …) |
| `xlsx` | Excel → Markdown (openpyxl) |
| `image` | Image I/O for OCR pipelines (Pillow) |
| `image-ocr` | Heavy OCR backends (pytesseract, paddle, easyocr, …) |
| `text` | TXT / JSON / XML converter (stdlib-oriented; marker extra) |
| `archive` | ZIP → Markdown layout (Pillow; optional tesseract for inline image OCR) |
| `url` | HTTP(S) HTML → Markdown (httpx, readability-lxml, markdownify, BeautifulSoup, lxml) |
| `url-full` | `url` plus PDF/Word/PPTX/XLSX/archive stack for **post-converting** downloaded linked files to Markdown |
| `audio` | **Audio → Markdown** via Whisper (`openai-whisper`); ships `imageio-ffmpeg` for a bundled **ffmpeg** when none is on `PATH` |
| `video` | **Video → Markdown** (ffmpeg extracts mono 16 kHz WAV, then same Whisper stack as `audio`) |
| `api` | FastAPI, uvicorn, httpx, pydantic-settings |
| `mcp` | MCP servers (`mcp`, `fastmcp` where used) |
| `graph` | **Graph → Markdown** (Neo4j Bolt + NetworkX GraphML/GML): `networkx`, `neo4j`, `pyyaml` |
| `dev` | pytest + API/MCP test helpers |
| `all` | Large superset of dependencies (use only if you need everything) |

Nested ZIP and office files inside archives require the corresponding extras (e.g. `archive` plus `pdf` for PDFs inside a ZIP).

---

## Command-line execution

All converters can be run from a terminal after you install the package (with the right **extras** for that format). Each tool is a normal executable on your `PATH` (no need to open Python yourself unless you choose the shim workflow below).

### 1. Install (once)

```bash
pip install "mdengine[pdf,word]"          # adjust extras: ppt, xlsx, image, archive, text, db, graph, …
# or from a clone:
pip install -e ".[pdf,word,archive]"
```

### 2. Check that the command is available

```bash
md-pdf --help
md-zip --help
```

If the shell reports “command not found”, ensure the Python **Scripts** directory is on your `PATH` (same place `pip` installs console scripts).

### 3. Commands (command-line entry points)

| Command | Implements | One-line example |
|---------|------------|------------------|
| `md-pdf` | `md_generator.pdf.converter:main` | `md-pdf report.pdf out.md` |
| `md-word` | `md_generator.word.converter:main` | `md-word notes.docx body.md` |
| `md-ppt` | `md_generator.ppt.converter:main` | `md-ppt deck.pptx ./ppt-out` |
| `md-xlsx` | `md_generator.xlsx.converter:main` | `md-xlsx -i data.xlsx -o ./excel-out` (also **`.csv`**) |
| `md-image` | `md_generator.image.converter:main` | `md-image ./scans page.md` |
| `md-text` | `md_generator.text.converter:main` | `md-text config.xml out.md` |
| `md-zip` | `md_generator.archive.converter:main` | `md-zip bundle.zip ./zip-out` |
| `md-url` | `md_generator.url.converter:main` | `md-url https://example.com/doc ./web-out --artifact-layout` |
| `md-audio` | `md_generator.media.audio.converter:main` | `md-audio clip.mp3 transcript.md --model base` |
| `md-video` | `md_generator.media.video.converter:main` | `md-video clip.mp4 transcript.md --model base` |
| `md-youtube` | `md_generator.media.youtube.converter:main` | `md-youtube "https://youtu.be/…" out.md --transcript-lang en` |
| `md-audio-api` | `md_generator.media.audio.api.run:main` | REST + MCP on port **8011** (see [Audio and video to Markdown](#audio-and-video-to-markdown)) |
| `md-video-api` | `md_generator.media.video.api.run:main` | REST + MCP on port **8012** |
| `md-youtube-api` | `md_generator.media.youtube.api.run:main` | REST + MCP on port **8013** (JSON `url` body; see same section) |
| `md-audio-mcp` | `md_generator.media.audio.api.mcp_server:main` | Standalone MCP (`--transport stdio` \| `sse` \| `streamable-http`) |
| `md-video-mcp` | `md_generator.media.video.api.mcp_server:main` | Same for video |
| `md-youtube-mcp` | `md_generator.media.youtube.api.mcp_server:main` | Same for YouTube (`youtube_url_to_markdown`) |
| `md-db` | `md_generator.db.cli.main:main` | `pip install "mdengine[db]"` then `md-db --config db.yaml` (or `mdengine db-to-md …`) |
| `md-db-api` | `md_generator.db.api.run:main` | FastAPI on port **8010** (`DB_TO_MD_PORT`): `POST /db-to-md/run`, `POST /db-to-md/run/sqlite` (upload + ZIP), `POST /db-to-md/job`, `POST /db-to-md/job/sqlite` (upload + async job), SSE `/db-to-md/job/{id}/events` |
| `md-db-mcp` | `md_generator.db.api.mcp_server:main` | Standalone MCP for metadata export tools |
| `md-graph` | `md_generator.graph.cli.main:main` | `pip install "mdengine[graph]"` then `md-graph --source neo4j --uri bolt://…` (or `mdengine graph-to-md …`) |
| `md-graph-api` | `md_generator.graph.api.run:main` | FastAPI on port **8012** (`GRAPH_TO_MD_PORT`): `POST /graph-to-md/run`, `/graph-to-md/job`, SSE `/graph-to-md/job/{id}/events` |
| `md-graph-mcp` | `md_generator.graph.api.mcp_server:main` | Standalone MCP for graph export tools |
| `md-api` | `md_generator.openapi.cli.main:main` | `pip install "mdengine[openapi]"` then `md-api generate --file openapi.yaml --output ./docs` (or `mdengine openapi-to-md generate …`) |
| `md-api-api` | `md_generator.openapi.api.run:main` | FastAPI on port **8015** (`OPENAPI_TO_MD_PORT`): `POST /openapi-to-md/generate` (OpenAPI upload → ZIP), `/health`, MCP at **`/mcp`** |
| `md-api-mcp` | `md_generator.openapi.api.mcp_server:main` | Standalone MCP: `api_validate_openapi_yaml`, `api_generate_readme_markdown`, `api_run_sync_zip_base64` |
| `mdengine` | `md_generator.engine_cli:main` | `mdengine db-to-md …` / `mdengine graph-to-md …` / `mdengine openapi-to-md generate …` |

**db-to-md ER diagrams:** add **`erd`** to the export feature list (YAML `features.include`, API body, or CLI `--include …,erd`). **Preferred:** **Graphviz** (`dot` on `PATH`, or **`GRAPHVIZ_DOT`**) produces `erd/*.dot`, `erd/*.png`, and `erd/*.svg`. **If Graphviz is missing,** the exporter falls back to **Mermaid** (`erDiagram`): it writes `erd/*.mermaid` plus a fenced **`erd/*.md`** for GitHub-style preview. With **`mermaid-py`** (included in `mdengine[db]`), it also requests **PNG/SVG** via mermaid.ink (requires network unless you self-host mermaid.ink and set **`MERMAID_INK_SERVER`** per [mermaid-py](https://pypi.org/project/mermaid-py/)). Tune **`erd.max_tables`** (default 100) and **`erd.scope`** (`full` \| `per_schema` \| `per_table`) under `erd:` in YAML; CLI: `--erd-max-tables`, `--erd-scope`. Async job SSE uses `progress_update` with `current` starting with `erd:`.

**db-to-md split exports and README merge:** with **`output.split_files: true`**, set **`output.write_combined_feature_markdown: true`** to also write root-level combined Markdown (for example `tables.md`, `functions.md`, `indexes.md`, and feature-specific paths such as `oracle/packages.md` or `mongodb/collections.md` when those features run). Set **`output.readme_feature_merge`** to **`inline`** (append full bundle bodies into `README.md`) or **`toc`** (append a linked list to those files). If merge is not **`none`** and split files are on, combined bundle writes are turned on automatically when loading config. CLI: `--write-combined-feature-markdown`, `--readme-feature-merge none|inline|toc`.

**db-to-md SQLite:** set **`database.type: sqlite`** and **`database.uri`** to a SQLAlchemy URL such as **`sqlite:///my.db`** or **`sqlite:////C:/data/my.db`**. The default SQLite catalog is **`main`**; packaged YAML that still has **`schema: public`** is normalized to **`main`** when the type is SQLite. CLI: **`--type sqlite`**. Stored routines, sequences, and partitions are not used by SQLite and stay empty; tables, indexes, views, triggers, and ERD (via FK introspection) follow the same export path as other SQL engines.

**db-to-md API SQLite upload:** **`POST /db-to-md/run/sqlite`** — `multipart/form-data` with field **`file`** (the `.sqlite` / `.db` bytes; must start with the standard `SQLite format 3` header) and optional **`config`** (JSON string with the same shape as a normal run body minus `database`: `schema`, `output`, `features`, `execution`, `limits`, `erd`). Returns the metadata ZIP immediately. **`POST /db-to-md/job/sqlite`** — same form fields; saves the file under the job workspace and runs the existing job pipeline (`GET /db-to-md/job/{id}/download` when complete). Upload size cap: env **`DB_TO_MD_MAX_SQLITE_UPLOAD_MB`** (default **256**). Large ZIPs may still require the async job path if they exceed **`DB_TO_MD_MAX_SYNC_ZIP_MB`** on the sync upload route.

**graph-to-md (Neo4j + NetworkX):** library lives under [`md_generator/graph/`](src/md_generator/graph/). **Sources:** **`networkx`** (GraphML/GML via `graph.graph_file` or `--graph-file`) or **`neo4j`** (`graph.uri`, `graph.user`, `graph.password`, optional `graph.database` for `session(database=…)`). **Output layout:** by default **`output.combine_markdown: true`** writes **`nodes.md`**, **`relationship.md`**, and **`graph_summary.md`** (summary plus embedded nodes and relationships). Set **`combine_markdown: false`** or CLI **`--individual` / `--markdown-layout individual`** for per-entity files under **`nodes/`** and **`relationships/`**. **Diagrams:** **`viz.mermaid: true`** (default) writes **`graph/graph.mmd`** and embeds a fenced Mermaid block in the export **`README.md`** (no Graphviz required). **`viz.enabled: true`** or CLI **`--viz`** also writes **`graph/graph.dot`** and runs **`dot`** for PNG/SVG/PDF when Graphviz is on `PATH` (or **`GRAPHVIZ_DOT`**). CLI **`--no-mermaid`** disables Mermaid; **`--depth`**, **`--start-node`**, **`--max-nodes`**, **`--max-edges`** bound traversal. Packaged defaults: [`src/md_generator/graph/config/default.yaml`](src/md_generator/graph/config/default.yaml). Tests: **`graph-to-md/tests/`**; API image: [`graph-to-md/Dockerfile.api`](graph-to-md/Dockerfile.api).

Every command accepts **`-h` / `--help`** for full flags (artifact layout, OCR, ZIP options, etc.).

### 4. Copy-paste examples (terminal)

**bash / macOS / Linux**

```bash
md-pdf manual.pdf ./artifact --artifact-layout
md-word letter.docx letter.md --images-dir ./letter-images
md-ppt slides.pptx ./ppt-artifact --artifact-layout
md-xlsx -i sales.xlsx -o ./md-sheets --split
md-xlsx -i export.csv -o ./csv-out
md-image ./photos ocr.md --engines tess --strategy best
md-text data.json data.md
md-zip archive.zip ./unzipped-md
md-url https://example.com/page ./page-bundle --artifact-layout
md-audio ./voice.mp3 ./voice.md --model tiny
md-video ./screen.mp4 ./screen.md --model base
pip install "mdengine[graph]" && md-graph --source neo4j --uri neo4j://localhost:7687 --user neo4j --password secret --database neo4j --output ./graph-out --viz
```

**Windows PowerShell** (same commands; use backslashes for paths if you prefer)

```powershell
md-pdf .\manual.pdf .\out\doc.md
md-zip .\archive.zip .\zip-out
md-url https://example.com/page .\page-bundle --artifact-layout
md-audio .\voice.mp3 .\voice.md --model tiny
md-video .\screen.mp4 .\screen.md --model base
pip install "mdengine[graph]"
md-graph --source neo4j --uri neo4j://localhost:7687 --user neo4j --password secret --database neo4j --output .\graph-out --viz
```

**Windows CMD**

```cmd
md-pdf manual.pdf out\doc.md
md-zip archive.zip zip-out
md-url https://example.com/page page-bundle --artifact-layout
```

### 5. Run without `pip install` (repo clone + `PYTHONPATH`)

The folders `pdf-to-md/`, `word-to-md/`, `url-to-md/`, … contain a thin `converter.py` that calls the same code as `md-pdf`, `md-word`, etc. From the **repository root**, point Python at `src` so `md_generator` imports, then run the shim:

**PowerShell**

```powershell
$env:PYTHONPATH = "$PWD\src"
python pdf-to-md\converter.py input.pdf out.md
```

**CMD**

```cmd
set PYTHONPATH=src
python pdf-to-md\converter.py input.pdf out.md
```

**bash**

```bash
PYTHONPATH=src python pdf-to-md/converter.py input.pdf out.md
```

### 6. Convert every file in `docs/` (strictly command-line)

To process **all supported files** under the [`docs/`](docs/) folder using only the installed **`md-*`** tools (no Python snippets), use the batch driver:

| Platform | Command (run from **repository root** unless noted) |
|----------|------------------------------------------------------|
| Windows | `powershell -ExecutionPolicy Bypass -File scripts/run-docs-cli.ps1` |
| Windows | Or double-click / run [`docs/run-all-cli.cmd`](docs/run-all-cli.cmd) (changes to repo root, then runs the script on `docs\`) |
| macOS / Linux | `bash scripts/run-docs-cli.sh` |

Optional environment variables for the shell script: `DOCS_DIR`, `OUT_DIR`, `IMAGE_ENGINES` (default `tess`). PowerShell script parameters: `-DocsDir`, `-OutDir`, `-ImageEngines`.

Outputs are written to **`docs/cli-output/<basename>/`** (one subfolder per input file). **`.csv`** files are converted with **`md-xlsx`** (same engine as Excel). **`.md`** files are skipped.

---


## Python library

Import from `md_generator.<format>` after installing the matching extras.

### PDF

```python
from pathlib import Path
from md_generator.pdf.pdf_extract import ConvertOptions, convert_pdf
from md_generator.pdf.utils import resolve_output

pdf = Path("input.pdf")
out = resolve_output(Path("out-dir"), artifact_layout=True, images_dir=None)
convert_pdf(pdf, out, ConvertOptions(verbose=True))
```

### Word (DOCX)

```python
from pathlib import Path
from md_generator.word.converter import convert_docx_to_markdown

convert_docx_to_markdown(
    Path("input.docx"),
    Path("out/body.md"),
    images_dir=Path("out/images"),
    verbose=False,
)
```

### PowerPoint

```python
from pathlib import Path
from md_generator.ppt.convert_impl import convert_pptx
from md_generator.ppt.options import ConvertOptions

convert_pptx(
    Path("slides.pptx"),
    Path("artifact-dir"),
    ConvertOptions(artifact_layout=True, extract_embedded_deep=False),
)
```

### Excel

```python
from pathlib import Path
from md_generator.xlsx.convert_config import ConvertConfig
from md_generator.xlsx.converter_core import convert_excel_to_markdown

result = convert_excel_to_markdown(
    Path("book.xlsx"),
    Path("out-dir"),
    config=ConvertConfig(),
)
print(result.paths_written)
```

### Images (OCR)

```python
from pathlib import Path
from md_generator.image.convert_impl import ConvertOptions, convert_images

convert_images(
    Path("scan.png"),
    Path("out.md"),
    ConvertOptions(
        engines=("tess",),
        strategy="best",
        title="OCR",
        tess_lang="eng",
        tesseract_cmd=None,
        paddle_lang="en",
        paddle_use_angle_cls=True,
        easy_langs=("en",),
        verbose=False,
    ),
)
```

### Text / JSON / XML

```python
from pathlib import Path
from md_generator.text.convert_impl import convert_text_file
from md_generator.text.options import ConvertOptions

convert_text_file(
    Path("data.json"),
    Path("out.md"),
    ConvertOptions(artifact_layout=False, verbose=False),
)
```

### ZIP archive

```python
from pathlib import Path
from md_generator.archive.convert_impl import convert_zip
from md_generator.archive.options import ConvertOptions

convert_zip(
    Path("upload.zip"),
    Path("artifact-out"),
    ConvertOptions(
        enable_office=True,
        use_image_to_md=True,
        verbose=False,
    ),
)
```

`repo_root` on `ConvertOptions` is **deprecated and ignored**; converters are loaded in-process from `md_generator`.

---

## Audio and video to Markdown

Library code lives under **`md_generator.media`**: shared probing in [`document_converter.py`](src/md_generator/media/document_converter.py), **audio** in [`media/audio/`](src/md_generator/media/audio/) (Whisper + ffprobe / ffmpeg metadata), **video** in [`media/video/`](src/md_generator/media/video/) (ffmpeg extracts audio only; transcription always goes through the audio service—no duplicate Whisper path in video).

### System requirements

- **ffmpeg** (and **ffprobe** when available) on `PATH` for metadata and for **video** demux. If `ffprobe` is missing or misbehaving, metadata falls back to parsing `ffmpeg -i` stderr.
- Optional **`FFMPEG`** environment variable: absolute path to an `ffmpeg` executable (see [`resolve_ffmpeg_executable()`](src/md_generator/media/document_converter.py)).
- **GPU** is optional; Whisper runs on CPU if needed (may log FP16→FP32 on CPU).

### Install

```bash
pip install "mdengine[audio,api,mcp]"    # audio CLI + HTTP + MCP
pip install "mdengine[video,api,mcp]"   # video CLI + HTTP + MCP (same ML stack as audio)
pip install "mdengine[youtube,api,mcp]" # YouTube URL → Markdown (captions + metadata; optional Whisper fallback)
```

### Python library

**Audio** — structured result + Markdown:

```python
from pathlib import Path
from md_generator.media.audio import AudioToMarkdownService, AudioConverter

svc = AudioToMarkdownService(whisper_model="base")  # language omitted → Whisper auto-detect; pass e.g. language="en" to force
text = svc.to_markdown(Path("input.mp3"), title="My title")
svc.write_markdown(Path("input.mp3"), Path("out/transcript.md"))

result = svc.transcribe(Path("input.wav"))  # metadata + segments + plain_text
```

**Video** — extract → transcribe (via audio) → Markdown:

```python
from pathlib import Path
from md_generator.media.video import VideoToMarkdownService

svc = VideoToMarkdownService(whisper_model="base")  # transcription language omitted → auto-detect
md = svc.to_markdown(Path("input.mp4"), title=None)
svc.write_markdown(Path("input.mp4"), Path("out/transcript.md"))
```

**YouTube** — captions API + page metadata (BeautifulSoup / oEmbed); optional **yt-dlp + Whisper** when captions are missing (`mdengine[audio]` and `yt-dlp` on `PATH`, or `MD_YOUTUBE_YTDLP`):

```python
from md_generator.media.youtube import YouTubeToMarkdownService

svc = YouTubeToMarkdownService(whisper_model="base")
md = svc.to_markdown("https://www.youtube.com/watch?v=VIDEO_ID", transcript_languages=["en"])
svc.write_markdown("https://youtu.be/VIDEO_ID", Path("out/youtube.md"))
```

For file-based pipelines, [`YouTubeConverter`](src/md_generator/media/youtube/converter.py) reads a `.url` / `.yturl` / `.youtube` file (or a `.txt` whose first non-comment line is a YouTube URL) and implements [`DocumentConverter`](src/md_generator/media/document_converter.py).

Public symbols are also re-exported from [`md_generator.media`](src/md_generator/media/__init__.py) for ffprobe helpers (`ffprobe_json`, `VideoProbeResult`, …).

### REST API (FastAPI)

Each service exposes the same job pattern as other converters:

| Endpoint | Description |
|----------|-------------|
| `POST /convert/sync` | Multipart field **`file`**; returns **Markdown** body. Query: `whisper_model`, `language` (omit or `auto` for detection; pass a code to force), `title`. |
| `POST /convert/jobs` | Async upload; returns `{ "job_id", "status" }`. |
| `GET /convert/jobs/{job_id}` | Status JSON. |
| `GET /convert/jobs/{job_id}/download` | Markdown when `done`; workspace removed after download. |

**Audio** defaults: `MD_AUDIO_MAX_UPLOAD_MB=200`, `MD_AUDIO_MAX_SYNC_UPLOAD_MB=40`, `MD_AUDIO_API_PORT=8011`.  
**Video** defaults: `MD_VIDEO_MAX_UPLOAD_MB=500`, `MD_VIDEO_MAX_SYNC_UPLOAD_MB=80`, `MD_VIDEO_API_PORT=8012`.  
**YouTube** uses **JSON** (not multipart): `POST /convert/sync` and `POST /convert/jobs` accept `{"url":"https://www.youtube.com/watch?v=…","title":null,"transcript_languages":["en"],"enable_audio_fallback":true,"whisper_model":"base","language":null}`. Defaults: `MD_YOUTUBE_API_PORT=8013`, `MD_YOUTUBE_JOB_TTL_SECONDS`, `MD_YOUTUBE_CORS_ORIGINS`, `MD_YOUTUBE_TEMP_DIR`.

Run with the bundled runners (each call builds the app with **`factory=True`** for a clean MCP session manager):

```bash
md-audio-api --host 127.0.0.1 --port 8011
md-video-api --host 127.0.0.1 --port 8012
md-youtube-api --host 127.0.0.1 --port 8013
```

Or with Uvicorn directly (the ASGI app is built by **`create_app()`** so each worker gets its own MCP session manager):

```bash
uvicorn md_generator.media.audio.api.main:create_app --factory --host 127.0.0.1 --port 8011
uvicorn md_generator.media.video.api.main:create_app --factory --host 127.0.0.1 --port 8012
uvicorn md_generator.media.youtube.api.main:create_app --factory --host 127.0.0.1 --port 8013
```

The module also defines **`app = create_app()`** for a single-process target: `uvicorn md_generator.media.audio.api.main:app` (no `--factory`).

Swagger is at **`/docs`** when the app is running.

### MCP (stdio, SSE, streamable HTTP)

1. **With FastAPI** — start `md-audio-api`, `md-video-api`, or `md-youtube-api`; mount Streamable HTTP MCP at **`http://<host>:<port>/mcp`** (same host as REST).
2. **Standalone** — process speaks MCP only:

```bash
md-audio-mcp --transport stdio
md-audio-mcp --transport sse
md-audio-mcp --transport streamable-http
md-video-mcp --transport stdio
md-youtube-mcp --transport stdio
```

**Audio MCP tools:** `transcribe_audio_path`, `transcribe_audio_base64`.  
**Video MCP tools:** `transcribe_video_path`, `transcribe_video_base64`.  
**YouTube MCP tool:** `youtube_url_to_markdown`.

Equivalent modules: `python -m md_generator.media.audio.api.mcp_server`, `python -m md_generator.media.video.api.mcp_server`, `python -m md_generator.media.youtube.api.mcp_server`.

### Thin shims (repo clone)

[`audio-to-md/converter.py`](audio-to-md/converter.py), [`video-to-md/converter.py`](video-to-md/converter.py), and [`youtube-to-md/converter.py`](youtube-to-md/converter.py) delegate to the same `main` as `md-audio` / `md-video` / `md-youtube`. Tests and `pytest.ini` live under `audio-to-md/tests/`, `video-to-md/tests/`, and `youtube-to-md/tests/`. [`db-to-md/converter.py`](db-to-md/converter.py) delegates to `md-db`; tests live under `db-to-md/tests/`. **graph-to-md** uses `md-graph` / `mdengine graph-to-md` directly (no thin `converter.py` shim); tests live under [`graph-to-md/tests/`](graph-to-md/tests/). [`openapi-to-md/converter.py`](openapi-to-md/converter.py) delegates to `md-api`; tests live under [`openapi-to-md/tests/`](openapi-to-md/tests/); example OpenAPI and output notes: [`openapi-to-md/examples/`](openapi-to-md/examples/).

---

## HTTP API (FastAPI)

All format APIs follow a similar pattern:

- **`POST /convert/sync`** — upload a file (most converters) **or** send JSON (`url-to-md`); response is often a **ZIP** (artifact bundle) for larger formats.
- **`POST /convert/jobs`** — async job; returns `job_id`.
- **`GET /convert/jobs/{job_id}`** — status.
- **`GET /convert/jobs/{job_id}/download`** — download result when ready.

Upload field name is **`file`** (multipart form) for file-based converters. Use `httpx` or `curl -F "file=@path/to/file"`. **URL** conversion uses a **JSON** body (`url` or `urls`); see [url-to-md/README.md](url-to-md/README.md).

### Run with Uvicorn

Install `mdengine[api]` plus the format extra(s), then run the **`app`** object from the table below.

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
| Audio (Whisper) | `md_generator.media.audio.api.main:create_app` (use **`--factory`**) or `…main:app` | `audio`, `api`, `mcp` |
| Video (Whisper) | `md_generator.media.video.api.main:create_app` (use **`--factory`**) or `…main:app` | `video`, `api`, `mcp` |
| YouTube | `md_generator.media.youtube.api.main:create_app` (use **`--factory`**) or `…main:app` | `youtube`, `api`, `mcp` |

Examples:

```bash
uvicorn md_generator.pdf.api.main:app --host 127.0.0.1 --port 8001
uvicorn md_generator.word.api.main:app --host 127.0.0.1 --port 8002
uvicorn md_generator.archive.api.main:app --host 127.0.0.1 --port 8010
uvicorn md_generator.url.api.main:app --host 127.0.0.1 --port 8011
uvicorn md_generator.playwright.api.main:app --host 127.0.0.1 --port 8014
uvicorn md_generator.graph.api.main:app --host 127.0.0.1 --port 8012
uvicorn md_generator.openapi.api.main:app --host 127.0.0.1 --port 8015
uvicorn md_generator.media.audio.api.main:create_app --factory --host 127.0.0.1 --port 8011
uvicorn md_generator.media.video.api.main:create_app --factory --host 127.0.0.1 --port 8012
uvicorn md_generator.media.youtube.api.main:create_app --factory --host 127.0.0.1 --port 8013
```

**Port note:** **`md-graph-api`** and **`md-video-api`** both default to **8012**; set **`GRAPH_TO_MD_PORT`** or **`MD_VIDEO_API_PORT`** when you need both on one machine. **`md-api-api`** defaults to **8015** (`OPENAPI_TO_MD_PORT`) so it does not collide with **`md-youtube-api`** (**8013**) or **`md-playwright-api`** (**8014**).

### MCP over HTTP on the same server

These apps mount an MCP HTTP app at **`/mcp`** (Streamable HTTP / framework-specific). Start the API as above, then point an MCP client at `http://<host>:<port>/mcp` where supported.

### Environment variables (limits & CORS)

Prefixes differ per service (often read from a `.env` file next to the process):

| Service | Prefix | Examples |
|---------|--------|----------|
| PDF | `PDF_TO_MD_` | `PDF_TO_MD_MAX_UPLOAD_MB`, `PDF_TO_MD_MAX_SYNC_UPLOAD_MB`, `PDF_TO_MD_TEMP_DIR`, `PDF_TO_MD_CORS_ORIGINS` |
| Word | `WORD_TO_MD_` | `WORD_TO_MD_MAX_UPLOAD_MB`, `WORD_TO_MD_MAX_SYNC_UPLOAD_MB`, `WORD_TO_MD_JOB_TTL_SECONDS`, `WORD_TO_MD_TEMP_DIR`, `WORD_TO_MD_CORS_ORIGINS` |
| ZIP | `ZIP_TO_MD_` | `ZIP_TO_MD_MAX_UPLOAD_MB`, `ZIP_TO_MD_MAX_SYNC_UPLOAD_MB`, `ZIP_TO_MD_JOB_TTL_SECONDS`, `ZIP_TO_MD_TEMP_DIR`, `ZIP_TO_MD_CORS_ORIGINS`, optional image post-pass defaults |
| PPTX | `PPT_TO_MD_` | `PPT_TO_MD_MAX_UPLOAD_MB`, … |
| Text | `TXT_JSON_XML_TO_MD_` | same pattern |
| XLSX | `XLSX_TO_MD_` | `XLSX_TO_MD_TEMP_DIR`, `XLSX_TO_MD_CORS_ORIGINS`, etc. (see `md_generator.xlsx.api.app`) |
| URL | `URL_TO_MD_` | `URL_TO_MD_MAX_SYNC_URLS`, `URL_TO_MD_MAX_SYNC_CRAWL_PAGES`, `URL_TO_MD_MAX_JOB_URLS`, `URL_TO_MD_JOB_TTL_SECONDS`, `URL_TO_MD_TEMP_DIR`, `URL_TO_MD_CORS_ORIGINS` |
| Playwright / SPA | `PLAYWRIGHT_TO_MD_` | `PLAYWRIGHT_TO_MD_MAX_SYNC_URLS`, `PLAYWRIGHT_TO_MD_MAX_JOB_URLS`, `PLAYWRIGHT_TO_MD_JOB_TTL_SECONDS`, `PLAYWRIGHT_TO_MD_TEMP_DIR`, `PLAYWRIGHT_TO_MD_CORS_ORIGINS`, `PLAYWRIGHT_TO_MD_API_HOST`, `PLAYWRIGHT_TO_MD_API_PORT` (default **8014**) |
| Database metadata | `DB_TO_MD_` | `DB_TO_MD_JOB_SQLITE_PATH`, `DB_TO_MD_JOB_WORKSPACE_ROOT`, `DB_TO_MD_CORS_ORIGINS`, `DB_TO_MD_MAX_SYNC_ZIP_MB`, `DB_TO_MD_HOST`, `DB_TO_MD_PORT` (default **8010**) |
| Graph metadata | `GRAPH_TO_MD_` | `GRAPH_TO_MD_JOB_SQLITE_PATH`, `GRAPH_TO_MD_JOB_WORKSPACE_ROOT`, `GRAPH_TO_MD_CORS_ORIGINS`, `GRAPH_TO_MD_MAX_SYNC_ZIP_MB`, `GRAPH_TO_MD_HOST`, `GRAPH_TO_MD_PORT` (default **8012**) |
| OpenAPI → Markdown | `OPENAPI_TO_MD_` | `OPENAPI_TO_MD_CORS_ORIGINS`, `OPENAPI_TO_MD_MAX_SYNC_ZIP_MB`, `OPENAPI_TO_MD_HOST`, `OPENAPI_TO_MD_PORT` (default **8015**) |
| Audio API | `MD_AUDIO_` | `MD_AUDIO_MAX_UPLOAD_MB`, `MD_AUDIO_MAX_SYNC_UPLOAD_MB`, `MD_AUDIO_JOB_TTL_SECONDS`, `MD_AUDIO_TEMP_DIR`, `MD_AUDIO_CORS_ORIGINS`, `MD_AUDIO_API_HOST`, `MD_AUDIO_API_PORT` |
| Video API | `MD_VIDEO_` | Same pattern as audio with `MD_VIDEO_*` (defaults: larger upload/sync caps, port **8012**) |
| YouTube API | `MD_YOUTUBE_` | `MD_YOUTUBE_JOB_TTL_SECONDS`, `MD_YOUTUBE_TEMP_DIR`, `MD_YOUTUBE_CORS_ORIGINS`, `MD_YOUTUBE_API_HOST`, `MD_YOUTUBE_API_PORT` (default **8013**); optional `MD_YOUTUBE_YTDLP` path for audio fallback |

Exact variable names match the `ApiSettings` / helper functions in each `api/settings` or `api/app` module.

---

## MCP (Model Context Protocol)

Two usage patterns:

1. **Bundled with FastAPI** — run Uvicorn as in the previous section; use path **`/mcp`** on the same host/port.
2. **Standalone process** — run a small `__main__` module (stdio, SSE, or streamable-http) for use with Cursor, Claude Desktop, or other MCP hosts.

### Standalone MCP processes

| Converter | Command (examples) |
|-----------|---------------------|
| ZIP | `python -m md_generator.archive.api.mcp_server` / `--transport sse` / `--transport streamable-http` |
| Text/JSON/XML | `python -m md_generator.text.api.mcp_server` |
| Word (FastMCP) | `python -m md_generator.word.api.mcp_server` / `--transport stdio` (default) or `streamable-http`, plus `--host` / `--port` when needed |
| PDF (FastMCP) | `python -m md_generator.pdf.api.mcp_server` / `--transport stdio` / `sse` / `streamable-http` |
| PPTX | `python -m md_generator.ppt.api.mcp_server` (see module docstring for flags) |
| Image | `python -m md_generator.image.api.mcp_server` (see module for CLI) |
| URL / HTML | `python -m md_generator.url.api.mcp_server` / `--transport sse` / `--transport streamable-http` |
| Playwright / SPA | `md-playwright-mcp` or `python -m md_generator.playwright.api.mcp_server` / `--transport sse` / `--transport streamable-http` |
| Audio | `md-audio-mcp` or `python -m md_generator.media.audio.api.mcp_server` — `--transport stdio` (default), `sse`, `streamable-http` |
| Video | `md-video-mcp` or `python -m md_generator.media.video.api.mcp_server` — same transports |
| YouTube | `md-youtube-mcp` or `python -m md_generator.media.youtube.api.mcp_server` — same transports |
| Database metadata | `md-db-mcp` or `python -m md_generator.db.api.mcp_server` — `--transport stdio` (default), `sse`, `streamable-http` |
| Graph (Neo4j / NetworkX) | `md-graph-mcp` or `python -m md_generator.graph.api.mcp_server` — `--transport stdio` (default), `sse`, `streamable-http` |
| OpenAPI → Markdown | `md-api-mcp` or `python -m md_generator.openapi.api.mcp_server` — `--transport stdio` (default), `sse`, `streamable-http` |

**Word** and **XLSX** also ship a small runner script in the repo:

```bash
python word-to-md/run.py api --host 127.0.0.1 --port 8002
python word-to-md/run.py mcp --transport stdio

python xlsx-to-md/run.py api --port 8003
python xlsx-to-md/run.py mcp --transport stdio
```

The XLSX MCP server is built in code (`build_mcp_server()` in `md_generator.xlsx.mcp_server`) and is mounted on the XLSX FastAPI app when MCP dependencies are installed.

Install **`mdengine[mcp]`** (and usually **`[api]`** when using HTTP) for MCP-related imports to resolve.

---

## Development

```bash
pip install -e ".[dev,all]"   # or a smaller subset of extras
python -m pytest
```

Tests live under each legacy folder’s `tests/` directory (e.g. `pdf-to-md/tests/`), **`graph-to-md/tests/`**, and **`openapi-to-md/tests/`**; `pyproject.toml` configures `pythonpath = ["src"]` so `md_generator` resolves without a separate `PYTHONPATH`.

---

## Repository layout

| Path | Role |
|------|------|
| `LICENSE` | MIT license text |
| `CODE_OF_CONDUCT.md` | [Contributor Covenant](https://www.contributor-covenant.org/) 2.1 |
| `src/md_generator/` | **Library source** (all formats + `api` subpackages); **audio/video** under [`media/audio/`](src/md_generator/media/audio/) and [`media/video/`](src/md_generator/media/video/); **graph-to-md** under [`graph/`](src/md_generator/graph/) |
| `pyproject.toml` | Packaging, extras, CLI entry points, pytest |
| `*-to-md/` | **Docs, tests, fixtures**, thin `converter.py` shims, some `run.py` helpers |
| `README.md` | This document |

For deeper behavior per format, see the original README files under each `*-to-md/` folder where they still exist.

---

## Legal

This project is released under the [MIT License](LICENSE). A copy of the license text is included in the repository root.
