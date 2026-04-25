from __future__ import annotations

import asyncio
import json
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from md_generator.db.api.schemas import DbToMdRunBody
from md_generator.db.api.settings import DbApiSettings, cors_list, sqlite_path_resolved
from md_generator.db.api.sqlite_upload import parse_sqlite_upload_config_json
from md_generator.db.core.job_manager import JobManager
from md_generator.db.core.util import is_sqlite_database_bytes, sqlite_uri_for_path
from md_generator.db.core.zip_export import build_markdown_zip_bytes
from md_generator.db.mcp.server import build_mcp_stack
from md_generator.db.mcp.sse import format_sse

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = DbApiSettings()
    ws = Path(settings.job_workspace_root) if settings.job_workspace_root else None
    jobs = JobManager(sqlite_path=sqlite_path_resolved(settings), workspace_root=ws)
    app.state.settings = settings
    app.state.jobs = jobs
    async with _mcp.session_manager.run():
        yield
    jobs.close()


app = FastAPI(title="db-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap = DbApiSettings()
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


@app.post("/db-to-md/run/sqlite")
async def db_run_sqlite_upload(
    request: Request,
    file: UploadFile = File(..., description="SQLite .db / .sqlite file (SQLite format 3)"),
    config: str | None = Form(None, description="Optional JSON object: schema, output, features, execution, limits, erd"),
) -> Response:
    """Sync export: upload a SQLite file, run db-to-md, return a ZIP (same limits as ``/db-to-md/run``)."""
    import tempfile

    settings: DbApiSettings = request.app.state.settings
    max_upload = max(1, settings.max_sqlite_upload_mb) * 1024 * 1024
    data = await file.read()
    if len(data) > max_upload:
        raise HTTPException(
            status_code=413,
            detail=f"SQLite upload exceeds DB_TO_MD_MAX_SQLITE_UPLOAD_MB ({settings.max_sqlite_upload_mb})",
        )
    if not is_sqlite_database_bytes(data):
        raise HTTPException(
            status_code=400,
            detail="File is not a SQLite database (expected 'SQLite format 3' header)",
        )
    try:
        opts = parse_sqlite_upload_config_json(config)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        with tempfile.TemporaryDirectory() as td:
            dbp = Path(td) / "upload.sqlite"
            dbp.write_bytes(data)
            uri = sqlite_uri_for_path(dbp)
            cfg = opts.to_run_config(uri)
            zip_data = build_markdown_zip_bytes(cfg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(zip_data) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP exceeds DB_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /db-to-md/job/sqlite",
        )
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="db-metadata.zip"'},
    )


@app.post("/db-to-md/job/sqlite")
async def db_job_sqlite_upload(
    request: Request,
    file: UploadFile = File(..., description="SQLite .db / .sqlite file (SQLite format 3)"),
    config: str | None = Form(None, description="Optional JSON object: schema, output, features, execution, limits, erd"),
) -> dict[str, str]:
    """Async job: save upload under the job workspace, run export, then ``GET …/download`` for the ZIP."""
    settings: DbApiSettings = request.app.state.settings
    jobs: JobManager = request.app.state.jobs
    max_upload = max(1, settings.max_sqlite_upload_mb) * 1024 * 1024
    data = await file.read()
    if len(data) > max_upload:
        raise HTTPException(
            status_code=413,
            detail=f"SQLite upload exceeds DB_TO_MD_MAX_SQLITE_UPLOAD_MB ({settings.max_sqlite_upload_mb})",
        )
    if not is_sqlite_database_bytes(data):
        raise HTTPException(
            status_code=400,
            detail="File is not a SQLite database (expected 'SQLite format 3' header)",
        )
    try:
        opts = parse_sqlite_upload_config_json(config)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    cfg_template = opts.to_run_config("sqlite:///placeholder")
    try:
        rec = jobs.create_sqlite_file_job(data, cfg_template)
        jobs.run_job_thread(rec.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"job_id": rec.job_id}


@app.post("/db-to-md/run")
async def db_run_sync(request: Request, body: DbToMdRunBody) -> Response:
    settings: DbApiSettings = request.app.state.settings
    cfg = body.to_run_config()
    try:
        data = build_markdown_zip_bytes(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP exceeds DB_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /db-to-md/job",
        )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="db-metadata.zip"'},
    )


@app.post("/db-to-md/job")
async def db_job_create(request: Request, body: DbToMdRunBody) -> dict[str, str]:
    jobs: JobManager = request.app.state.jobs
    cfg = body.to_run_config()
    try:
        rec = jobs.create_job(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    jobs.run_job_thread(rec.job_id)
    return {"job_id": rec.job_id}


@app.get("/db-to-md/job/{job_id}")
async def db_job_status(request: Request, job_id: str) -> dict:
    jobs: JobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    return rec.to_api_dict()


@app.get("/db-to-md/job/{job_id}/download")
async def db_job_download(request: Request, job_id: str) -> FileResponse:
    jobs: JobManager = request.app.state.jobs
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
        filename="db-metadata.zip",
        background=task,
    )


@app.get("/db-to-md/job/{job_id}/events")
async def db_job_events(request: Request, job_id: str) -> StreamingResponse:
    jobs: JobManager = request.app.state.jobs

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


@app.get("/db-to-md/job/{job_id}/stream")
async def db_job_stream(request: Request, job_id: str) -> StreamingResponse:
    jobs: JobManager = request.app.state.jobs

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
