from __future__ import annotations

import asyncio
import io
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from md_generator.xlsx.convert_config import ConvertConfig, ExcelMaxRows
from md_generator.xlsx.converter_core import convert_excel_to_markdown

_executor = ThreadPoolExecutor(max_workers=4)

_HAS_MCP = False
_mcp_app: Any = None

try:
    from md_generator.xlsx.mcp_server import build_mcp_server

    _mcp_server = build_mcp_server()
    _mcp_app = _mcp_server.streamable_http_app()
    _HAS_MCP = True
except ImportError:
    _mcp_server = None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(f"XLSX_TO_MD_{name}")
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_str(name: str, default: str) -> str:
    return os.environ.get(f"XLSX_TO_MD_{name}", default)


def _temp_root() -> Path:
    d = _env_str("TEMP_DIR", "")
    return Path(d) if d else Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if _HAS_MCP and _mcp_app is not None:
        async with _mcp_app.router.lifespan_context(_mcp_app):
            yield
    else:
        yield


app = FastAPI(title="xlsx-to-md", version="1.0.0", lifespan=_lifespan)

_origins = _env_str("CORS_ORIGINS", "").strip()
if _origins:
    _allow = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allow,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if _HAS_MCP and _mcp_app is not None:
    app.mount("/mcp", _mcp_app)


def _config_from_query(
    *,
    split: bool = False,
    include_hidden_sheets: bool = False,
    include_toc: bool = True,
    streaming: bool = False,
    expand_merged_cells: bool = True,
    max_rows_per_sheet: int = ExcelMaxRows,
    sheet: list[str] | None = None,
) -> ConvertConfig:
    return ConvertConfig(
        split_by_sheet=split,
        include_hidden_sheets=include_hidden_sheets,
        include_toc=include_toc,
        streaming=streaming,
        expand_merged_cells=expand_merged_cells,
        max_rows_per_sheet=max_rows_per_sheet,
        sheet_names=sheet or None,
    )


async def _read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        block = await upload.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Upload exceeds size limit")
        chunks.append(block)
    return b"".join(chunks)


def _zip_paths(paths: list[Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)
    return buf.getvalue()


def _run_convert_sync(src: Path, out_dir: Path, cfg: ConvertConfig):
    return convert_excel_to_markdown(src, out_dir, config=cfg)


class _JobState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}

    def cleanup(self) -> None:
        ttl = _env_int("JOB_TTL_SECONDS", 3600)
        now = time.time()
        dead: list[str] = []
        for jid, data in self.jobs.items():
            if now - data["created"] > ttl:
                dead.append(jid)
                td = data.get("work_dir")
                if isinstance(td, Path) and td.is_dir():
                    shutil.rmtree(td, ignore_errors=True)
        for jid in dead:
            self.jobs.pop(jid, None)


_jobs = _JobState()


@app.post("/convert/sync")
async def convert_sync(
    file: UploadFile = File(...),
    split: bool = Query(False),
    include_hidden_sheets: bool = Query(False),
    include_toc: bool = Query(True),
    streaming: bool = Query(False),
    expand_merged_cells: bool = Query(True),
    max_rows_per_sheet: int = Query(ExcelMaxRows, ge=1, le=ExcelMaxRows),
    sheet: list[str] | None = Query(None),
):
    name = file.filename or ""
    if not name.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(status_code=400, detail="Filename must end with .xlsx, .xlsm, or .csv")

    max_mb = _env_int("MAX_SYNC_UPLOAD_MB", 50)
    raw = await _read_upload(file, max_mb * 1024 * 1024)

    cfg = _config_from_query(
        split=split,
        include_hidden_sheets=include_hidden_sheets,
        include_toc=include_toc,
        streaming=streaming,
        expand_merged_cells=expand_merged_cells,
        max_rows_per_sheet=max_rows_per_sheet,
        sheet=sheet,
    )

    tmp = Path(tempfile.mkdtemp(dir=str(_temp_root())))
    try:
        src = tmp / Path(name).name
        src.write_bytes(raw)
        out = tmp / "out"
        out.mkdir()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(_executor, _run_convert_sync, src, out, cfg)
        data = _zip_paths(result.paths_written)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return Response(content=data, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=convert.zip"})


@app.post("/convert/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    split: bool = Query(False),
    include_hidden_sheets: bool = Query(False),
    include_toc: bool = Query(True),
    streaming: bool = Query(False),
    expand_merged_cells: bool = Query(True),
    max_rows_per_sheet: int = Query(ExcelMaxRows, ge=1, le=ExcelMaxRows),
    sheet: list[str] | None = Query(None),
):
    name = file.filename or ""
    if not name.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(status_code=400, detail="Filename must end with .xlsx, .xlsm, or .csv")

    max_mb = _env_int("MAX_UPLOAD_MB", 200)
    raw = await _read_upload(file, max_mb * 1024 * 1024)

    cfg = _config_from_query(
        split=split,
        include_hidden_sheets=include_hidden_sheets,
        include_toc=include_toc,
        streaming=streaming,
        expand_merged_cells=expand_merged_cells,
        max_rows_per_sheet=max_rows_per_sheet,
        sheet=sheet,
    )

    jid = str(uuid.uuid4())
    work = Path(tempfile.mkdtemp(dir=str(_temp_root())))
    src = work / Path(name).name
    src.write_bytes(raw)
    out = work / "out"
    out.mkdir()

    async with _jobs.lock:
        _jobs.cleanup()
        _jobs.jobs[jid] = {
            "status": "pending",
            "message": "",
            "zip_path": None,
            "work_dir": work,
            "created": time.time(),
        }

    async def _run() -> None:
        async with _jobs.lock:
            if jid not in _jobs.jobs:
                return
            _jobs.jobs[jid]["status"] = "running"
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(_executor, _run_convert_sync, src, out, cfg)
            zp = work / "result.zip"
            zp.write_bytes(_zip_paths(result.paths_written))
            async with _jobs.lock:
                if jid in _jobs.jobs:
                    _jobs.jobs[jid]["status"] = "done"
                    _jobs.jobs[jid]["zip_path"] = zp
                    _jobs.jobs[jid]["message"] = "ok"
        except Exception as e:
            async with _jobs.lock:
                if jid in _jobs.jobs:
                    _jobs.jobs[jid]["status"] = "error"
                    _jobs.jobs[jid]["message"] = str(e)

    background_tasks.add_task(_run)
    return {"id": jid}


@app.get("/convert/jobs/{job_id}")
async def get_job(job_id: str):
    async with _jobs.lock:
        _jobs.cleanup()
        job = _jobs.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {
        "id": job_id,
        "status": job["status"],
        "message": job["message"],
    }


@app.get("/convert/jobs/{job_id}/download")
async def download_job(job_id: str):
    async with _jobs.lock:
        job = _jobs.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Job not finished")
    zp = job.get("zip_path")
    if not isinstance(zp, Path) or not zp.is_file():
        raise HTTPException(status_code=500, detail="ZIP missing")
    data = zp.read_bytes()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={job_id}.zip"},
    )
