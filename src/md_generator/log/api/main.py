from __future__ import annotations

import asyncio
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from md_generator.log.api.schemas import LogToMdRunBody, parse_log_upload_config_json
from md_generator.log.api.settings import LogApiSettings, cors_list, sqlite_path_resolved
from md_generator.log.core.job_manager import LogJobManager
from md_generator.log.core.zip_export import build_log_markdown_zip_bytes
from md_generator.log.mcp.server import build_mcp_stack
from md_generator.log.mcp.sse import format_sse
_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = LogApiSettings()
    ws = Path(settings.job_workspace_root) if settings.job_workspace_root else None
    jobs = LogJobManager(sqlite_path=sqlite_path_resolved(settings), workspace_root=ws)
    app.state.settings = settings
    app.state.jobs = jobs
    async with _mcp.session_manager.run():
        yield
    jobs.close()


app = FastAPI(title="log-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap = LogApiSettings()
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


@app.post("/log-to-md/run")
async def log_run_sync(request: Request, body: LogToMdRunBody) -> Response:
    settings: LogApiSettings = request.app.state.settings
    cfg = body.to_log_run_config()
    if not cfg.input.paths:
        raise HTTPException(status_code=400, detail="input.paths is required for /log-to-md/run")
    try:
        zip_data = build_log_markdown_zip_bytes(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(zip_data) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP exceeds LOG_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /log-to-md/job/upload",
        )
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="log-markdown.zip"'},
    )


@app.post("/log-to-md/job")
async def log_job_create(request: Request, body: LogToMdRunBody) -> dict[str, str]:
    jobs: LogJobManager = request.app.state.jobs
    cfg = body.to_log_run_config()
    if not cfg.input.paths:
        raise HTTPException(status_code=400, detail="input.paths is required for /log-to-md/job")
    try:
        rec = jobs.create_job(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    jobs.run_job_thread(rec.job_id)
    return {"job_id": rec.job_id}


@app.post("/log-to-md/run/upload")
async def log_run_upload(
    request: Request,
    file: UploadFile = File(..., description="Plain-text .log or .txt"),
    config: str | None = Form(None, description="Optional JSON (same shape as /log-to-md/run body minus input paths)"),
) -> Response:
    settings: LogApiSettings = request.app.state.settings
    max_upload = max(1, settings.max_log_upload_mb) * 1024 * 1024
    data = await file.read()
    if len(data) > max_upload:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds LOG_TO_MD_MAX_LOG_UPLOAD_MB ({settings.max_log_upload_mb})",
        )
    try:
        opts = parse_log_upload_config_json(config)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as td:
            logp = Path(td) / (file.filename or "upload.log")
            logp.write_bytes(data)
            cfg = opts.to_log_run_config()
            from dataclasses import replace

            cfg = replace(cfg, input=replace(cfg.input, paths=[str(logp)]))
            cfg = replace(cfg, output=replace(cfg.output, path=str(Path(td) / "out")))
            zip_data = build_log_markdown_zip_bytes(cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(zip_data) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP exceeds LOG_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /log-to-md/job/upload",
        )
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="log-markdown.zip"'},
    )


@app.post("/log-to-md/job/upload")
async def log_job_upload(
    request: Request,
    file: UploadFile = File(...),
    config: str | None = Form(None),
) -> dict[str, str]:
    settings: LogApiSettings = request.app.state.settings
    jobs: LogJobManager = request.app.state.jobs
    max_upload = max(1, settings.max_log_upload_mb) * 1024 * 1024
    data = await file.read()
    if len(data) > max_upload:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds LOG_TO_MD_MAX_LOG_UPLOAD_MB ({settings.max_log_upload_mb})",
        )
    try:
        opts = parse_log_upload_config_json(config)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    tpl = opts.to_log_run_config()
    try:
        rec = jobs.create_upload_job(data, tpl, filename=file.filename or "upload.log")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    jobs.run_job_thread(rec.job_id)
    return {"job_id": rec.job_id}


@app.get("/log-to-md/job/{job_id}")
async def log_job_status(request: Request, job_id: str) -> dict:
    jobs: LogJobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    return rec.to_api_dict()


@app.get("/log-to-md/job/{job_id}/download")
async def log_job_download(request: Request, job_id: str) -> FileResponse:
    jobs: LogJobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    if rec.status != "COMPLETED" or not rec.zip_path:
        raise HTTPException(400, detail="Job is not ready for download")
    path = Path(rec.zip_path)
    if not path.is_file():
        raise HTTPException(400, detail="ZIP missing on disk")
    task = BackgroundTask(jobs.remove_after_download, job_id)
    return FileResponse(
        path,
        media_type="application/zip",
        filename="log-markdown.zip",
        background=task,
    )


@app.get("/log-to-md/job/{job_id}/events")
async def log_job_events(request: Request, job_id: str) -> StreamingResponse:
    jobs: LogJobManager = request.app.state.jobs

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
                yield format_sse(
                    "job_completed",
                    {"job_id": job_id, "zip_path": rec.zip_path},
                ).encode("utf-8")
                return
            if rec.status == "FAILED":
                yield format_sse(
                    "job_failed",
                    {"job_id": job_id, "error": rec.error or "unknown"},
                ).encode("utf-8")
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/log-to-md/job/{job_id}/stream")
async def log_job_stream(request: Request, job_id: str) -> StreamingResponse:
    jobs: LogJobManager = request.app.state.jobs

    async def gen():
        while True:
            rec = jobs.get(job_id)
            if not rec:
                yield b"# error: unknown job\n"
                return
            if rec.status == "FAILED":
                yield (f"# job failed\n{rec.error or ''}\n").encode("utf-8")
                return
            if rec.status == "COMPLETED" and rec.zip_path:
                zp = Path(rec.zip_path)
                with zipfile.ZipFile(zp, "r") as zf:
                    for name in sorted(zf.namelist()):
                        if name.endswith(".md"):
                            hdr = f"\n\n---\n# file: {name}\n---\n\n".encode("utf-8")
                            yield hdr
                            yield zf.read(name)
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
