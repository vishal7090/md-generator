# xlsx-to-md

Convert Excel workbooks (`.xlsx`, `.xlsm`) to GitHub-flavored Markdown: one combined file or one file per worksheet, optional JSON configuration, merged-cell expansion, hidden-sheet filtering, and column selection.

## Setup

```bash
cd xlsx-to-md
pip install -r requirements.txt
```

For the **HTTP API** (FastAPI, OpenAPI/Swagger, ZIP download, MCP at `/mcp`):

```bash
pip install -r requirements.txt -r requirements-api.txt
```

MCP-only (stdio server): `pip install -r requirements.txt -r requirements-mcp.txt`

## CLI

**Option A — unified runner** (subcommands):

```bash
python run.py cli -- --input path/to/workbook.xlsx --output-dir ./out
```

**Option B — direct script** (same as before, no subcommand):

```bash
python converter.py --input path/to/workbook.xlsx --output-dir ./out
```

**Option C — module:**

```bash
python -m src.converter --input workbook.xlsx --output-dir ./out
```

Common flags:

| Flag | Description |
|------|-------------|
| `--split` | Write one `.md` per sheet (files named from slugified sheet titles). |
| `--config path.json` | Load [ConvertConfig](#json-configuration) defaults. |
| `--include-hidden-sheets` | Include `hidden` / `veryHidden` worksheets. |
| `--no-toc` | Omit the table of contents (combined output, multiple sheets). |
| `--streaming` | Use OpenPyXL read-only iteration (does **not** expand merged cells). |
| `--no-expand-merged` | Skip merged-cell fill (non-streaming load only). |
| `--max-rows N` | Cap rows per sheet (default **1,048,576** = Excel max, or from config). |
| `--sheet NAME` | Only export tab(s) with this name (case-insensitive); repeat for multiple. Default: all sheets. |
| `--log-level DEBUG` | Verbose logging. |

### Sample run

After placing a workbook such as `DealerLocation_Characteristics v1.5 (2).xlsx` on disk:

```bash
python converter.py -i "C:\path\to\DealerLocation_Characteristics v1.5 (2).xlsx" -o .\out
```

## HTTP API (FastAPI + ZIP + Swagger)

Start the server (default **port 8003** to avoid clashing with `word-to-md` on 8002):

```bash
python run.py api --host 127.0.0.1 --port 8003
```

- **Swagger UI:** http://127.0.0.1:8003/docs  
- **Sync ZIP:** `POST /convert/sync` — multipart field `file` (filename must end with `.xlsx` or `.xlsm`).  
- **Async job:** `POST /convert/jobs` → `GET /convert/jobs/{id}` → `GET /convert/jobs/{id}/download` when `status` is `done`.  
- **Query params** (same semantics as CLI): `split`, `include_hidden_sheets`, `include_toc`, `streaming`, `expand_merged_cells`, `max_rows_per_sheet`, `sheet` (repeat per tab name; case-insensitive; omit = all sheets).

The ZIP contains all generated `.md` files plus `conversion_log.txt`.

**Environment** (prefix `XLSX_TO_MD_`): `MAX_UPLOAD_MB`, `MAX_SYNC_UPLOAD_MB`, `JOB_TTL_SECONDS`, `TEMP_DIR`, `CORS_ORIGINS`.

## MCP (Streamable HTTP + standalone)

When the API is running, Streamable HTTP MCP is mounted at **`/mcp`** (same pattern as `word-to-md`).

Standalone MCP server:

```bash
python run.py mcp --transport stdio
# or: streamable-http | sse
```

Output: `out\DealerLocation_Characteristics v1.5 (2).md` (basename follows the input stem unless `output_basename` is set in config).

## JSON configuration

See [examples/sample-config.json](examples/sample-config.json). Load with `--config examples/sample-config.json`.

| Field | Type | Description |
|-------|------|-------------|
| `include_hidden_sheets` | bool | Default `false`. |
| `max_rows_per_sheet` | int | Default **1,048,576** (Excel row limit). |
| `sheet_names` | string[] or null | Only these tabs (case-insensitive); `null` = all sheets. |
| `split_by_sheet` | bool | Overridable with CLI `--split`. |
| `sheet_heading_level` | `"##"` or `"###"` | Sheet section heading level. |
| `include_toc` | bool | Table of contents for combined multi-sheet output. |
| `column_indices` | int[] or null | 0-based columns to keep (header row unchanged). |
| `column_names` | string[] or null | Header names to keep (first row must contain them). |
| `column_alignment` | `left`/`right`/`center`[] | Per-column alignment when `enable_alignment_in_tables` is true. |
| `enable_alignment_in_tables` | bool | Emit GFM alignment row (`:---`, `---:`, `:---:`). |
| `expand_merged_cells` | bool | Default `true`; repeat top-left value across merged range. |
| `streaming` | bool | Read-only mode; incompatible with merge expansion (auto-disabled with warning). |
| `output_basename` | string or null | Output filename for combined mode (e.g. `report.md`). |

CLI flags override config where noted (`--split`, `--no-toc`, etc.).

## Python API

```python
from pathlib import Path
from src import convert_excel_to_markdown
from src.convert_config import ConvertConfig

result = convert_excel_to_markdown(
    Path("workbook.xlsx"),
    Path("out"),
    split_by_sheet=False,
    config=ConvertConfig(include_toc=True),
)
print(result.paths_written, result.sheets_processed, result.warnings)
```

## Formulas

Workbooks are opened with `data_only=True`, so formula cells show **cached** values from the file. If values look stale, open and save the workbook in Excel (or equivalent) to refresh the cache.

## Traceability

Per project governance, you may store sample outputs or conversion logs under `.cursor/artifacts/<FeatureID>/` and reference the same FeatureID in change records.

## Tests

```bash
pytest
```

API tests require `pip install -r requirements-api.txt` (they skip if FastAPI is missing).

## Sample input/output

- **Input:** Any `.xlsx` / `.xlsm` (tests build minimal workbooks programmatically).
- **Output:** Combined Markdown with HTML sheet headings (`<h2 id="…">Sheet: …</h2>`) so table-of-contents links resolve reliably on GitHub.
