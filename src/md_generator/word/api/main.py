from __future__ import annotations

import io
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from md_generator.word.api.convert_util import (
    STAGING_DOCX_NAME,
    convert_upload_to_artifact_dir,
    stage_docx_bytes,
)
from md_generator.word.api.jobs import JobStore, run_job_in_thread
from md_generator.word.api.mcp_server import mcp
from md_generator.word.artifact import zip_artifact_directory
from md_generator.word.settings import WordToMdSettings, load_settings

mcp_http_app = mcp.http_app(path="/", transport="streamable-http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.job_store = JobStore(settings)
    async with mcp_http_app.lifespan(app):
        yield


app = FastAPI(title="word-to-md", version="1.0.0", lifespan=lifespan)


def _apply_cors(application: FastAPI, settings: WordToMdSettings) -> None:
    origins = list(settings.cors_origins) if settings.cors_origins else ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_apply_cors(app, load_settings())
app.mount("/mcp", mcp_http_app)


async def _read_upload_with_limit(upload: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    total = 0
    while True:
        chunk = await upload.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="File too large for synchronous conversion. Use POST /convert/jobs instead.",
            )
        data.extend(chunk)
    return bytes(data)


def _validate_docx_name(filename: str | None) -> None:
    if not filename or not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Multipart field 'file' must be a .docx filename")


@app.post("/convert/sync")
async def convert_sync(
    request: Request,
    file: UploadFile = File(...),
    page_break_as_hr: bool = True,
) -> StreamingResponse:
    settings: WordToMdSettings = request.app.state.settings
    _validate_docx_name(file.filename)
    max_bytes = int(settings.max_sync_upload_mb * 1024 * 1024)
    max_job_bytes = int(settings.max_upload_mb * 1024 * 1024)
    if max_bytes > max_job_bytes:
        max_bytes = max_job_bytes
    raw = await _read_upload_with_limit(file, max_job_bytes)
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail="File too large for synchronous conversion. Use POST /convert/jobs instead.",
        )

    workdir = Path(tempfile.mkdtemp(prefix="word-md-sync-", dir=settings.temp_dir))
    try:
        stage_docx_bytes(workdir / STAGING_DOCX_NAME, raw)
        convert_upload_to_artifact_dir(
            workdir / STAGING_DOCX_NAME,
            workdir,
            page_break_as_hr=page_break_as_hr,
        )
        zbytes = zip_artifact_directory(workdir)
    finally:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)

    return StreamingResponse(
        io.BytesIO(zbytes),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="artifact.zip"'},
    )


@app.post("/convert/jobs")
async def convert_create_job(
    request: Request,
    file: UploadFile = File(...),
    page_break_as_hr: bool = True,
) -> dict[str, str]:
    settings: WordToMdSettings = request.app.state.settings
    store: JobStore = request.app.state.job_store
    _validate_docx_name(file.filename)
    max_bytes = int(settings.max_upload_mb * 1024 * 1024)
    raw = await _read_upload_with_limit(file, max_bytes)

    workdir = Path(tempfile.mkdtemp(prefix="word-md-job-", dir=settings.temp_dir))
    stage_docx_bytes(workdir / STAGING_DOCX_NAME, raw)
    rec = store.create_job(workdir)

    def _work() -> None:
        try:
            convert_upload_to_artifact_dir(
                workdir / STAGING_DOCX_NAME,
                workdir,
                page_break_as_hr=page_break_as_hr,
            )
        except Exception:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)
            raise

    run_job_in_thread(rec.job_id, store, _work)
    return {"job_id": rec.job_id, "status": rec.status}


@app.get("/convert/jobs/{job_id}")
async def convert_job_status(request: Request, job_id: str) -> dict:
    store: JobStore = request.app.state.job_store
    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    out: dict = {"job_id": rec.job_id, "status": rec.status}
    if rec.error:
        out["error"] = rec.error
    return out


@app.get("/convert/jobs/{job_id}/download")
async def convert_job_download(request: Request, job_id: str) -> StreamingResponse:
    store: JobStore = request.app.state.job_store
    rec = store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if rec.status != "done":
        raise HTTPException(status_code=404, detail="Job is not finished")
    zbytes = zip_artifact_directory(rec.workdir)
    return StreamingResponse(
        io.BytesIO(zbytes),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="artifact.zip"'},
    )
