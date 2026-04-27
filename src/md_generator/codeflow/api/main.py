from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from md_generator.codeflow.api.job_manager import CodeflowJobManager
from md_generator.codeflow.api.schemas import merge_upload_options_json, options_to_scan_config
from md_generator.codeflow.api.settings import CodeflowApiSettings, cors_list, sqlite_path_resolved
from md_generator.codeflow.core.extractor import build_output_zip
from md_generator.codeflow.core.run_config import ScanConfig

try:
    from md_generator.codeflow.mcp.server import build_mcp_stack

    _mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)
except Exception:
    _mcp = None  # type: ignore[misc]
    _mcp_http = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = CodeflowApiSettings()
    ws = Path(settings.job_workspace_root) if settings.job_workspace_root else None
    jobs = CodeflowJobManager(sqlite_path=sqlite_path_resolved(settings), workspace_root=ws)
    app.state.settings = settings
    app.state.jobs = jobs
    if _mcp is not None:
        async with _mcp.session_manager.run():
            yield
    else:
        yield
    jobs.close()


app = FastAPI(title="codeflow-to-md", lifespan=lifespan)
if _mcp_http is not None:
    app.mount("/mcp", _mcp_http)

_bootstrap = CodeflowApiSettings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list(_bootstrap),
    allow_credentials="*" not in cors_list(_bootstrap),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    options_json: str | None = Form(default=None),
) -> dict[str, str]:
    """Upload a ZIP of source code; returns ``job_id`` for async processing."""
    settings: CodeflowApiSettings = request.app.state.settings
    jobs: CodeflowJobManager = request.app.state.jobs
    raw = await file.read()
    max_b = max(1, settings.max_upload_zip_mb) * 1024 * 1024
    if len(raw) > max_b:
        raise HTTPException(status_code=413, detail=f"ZIP exceeds CODEFLOW_MAX_UPLOAD_ZIP_MB ({settings.max_upload_zip_mb})")
    try:
        opts = merge_upload_options_json(options_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # template: output path overwritten in job manager
    tmp_src = Path(".")
    cfg_tpl = options_to_scan_config(tmp_src, "out", opts)
    try:
        rec = jobs.create_zip_job(raw, cfg_tpl)
        jobs.run_job_thread(rec.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"job_id": rec.job_id}


@app.get("/status/{job_id}")
async def job_status(request: Request, job_id: str) -> dict:
    jobs: CodeflowJobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    return rec.to_api_dict()


@app.get("/result/{job_id}")
async def job_result(request: Request, job_id: str) -> FileResponse:
    jobs: CodeflowJobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    if rec.status != "COMPLETED" or not rec.zip_path:
        raise HTTPException(400, detail="Job is not ready")
    path = Path(rec.zip_path)
    if not path.is_file():
        raise HTTPException(400, detail="ZIP missing on disk")
    return FileResponse(path, media_type="application/zip", filename="codeflow-output.zip")


@app.post("/analyze/sync")
async def analyze_sync(
    request: Request,
    file: UploadFile = File(...),
    options_json: str | None = Form(default=None),
) -> Response:
    """Small ZIP → immediate ZIP response (bounded by ``CODEFLOW_MAX_SYNC_ZIP_MB``)."""
    settings: CodeflowApiSettings = request.app.state.settings
    raw = await file.read()
    max_up = max(1, settings.max_upload_zip_mb) * 1024 * 1024
    if len(raw) > max_up:
        raise HTTPException(status_code=413, detail="ZIP too large")
    try:
        opts = merge_upload_options_json(options_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    import tempfile

    td = Path(tempfile.mkdtemp(prefix="codeflow-sync-"))
    src = td / "src"
    src.mkdir(parents=True, exist_ok=True)
    zin = td / "in.zip"
    zin.write_bytes(raw)
    import zipfile

    with zipfile.ZipFile(zin, "r") as zf:
        zf.extractall(src)
    cfg = options_to_scan_config(src, "out", opts)
    try:
        data = build_output_zip(cfg, workspace_root=src)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(status_code=413, detail=f"Output exceeds CODEFLOW_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /analyze")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="codeflow-output.zip"'},
    )


@app.get("/analyze/job/{job_id}/events")
async def job_events(request: Request, job_id: str) -> StreamingResponse:
    from md_generator.codeflow.api.sse import format_sse

    jobs: CodeflowJobManager = request.app.state.jobs

    async def gen():
        rec = jobs.get(job_id)
        if not rec:
            yield format_sse("job_failed", {"job_id": job_id, "error": "unknown job_id"}).encode("utf-8")
            return
        yield format_sse("job_started", {"job_id": job_id}).encode("utf-8")
        last_progress = -1
        while True:
            rec = jobs.get(job_id)
            if not rec:
                yield format_sse("job_failed", {"job_id": job_id, "error": "job disappeared"}).encode("utf-8")
                return
            if rec.progress != last_progress or rec.current:
                last_progress = rec.progress
                yield format_sse(
                    "progress_update",
                    {"progress": rec.progress, "current": rec.current},
                ).encode("utf-8")
            if rec.status == "COMPLETED":
                yield format_sse("job_completed", {"job_id": job_id, "zip_path": rec.zip_path}).encode("utf-8")
                return
            if rec.status == "FAILED":
                yield format_sse("job_failed", {"job_id": job_id, "error": rec.error or "unknown"}).encode("utf-8")
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream")
