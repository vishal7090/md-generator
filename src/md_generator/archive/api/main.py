from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from md_generator.archive.api.convert_runner import build_artifact_zip_bytes
from md_generator.archive.api.jobs import JobStore
from md_generator.archive.api.mcp_setup import build_mcp_stack
from md_generator.archive.api.query_options import convert_options_from_query
from md_generator.archive.api.settings import ApiSettings, cors_list
from md_generator.archive.options import DEFAULT_IMAGE_TO_MD_ENGINES

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = ApiSettings()
    base = Path(settings.temp_dir) if settings.temp_dir else None
    store = JobStore(base, settings.job_ttl_seconds)
    store.start_sweeper()
    app.state.settings = settings
    app.state.job_store = store
    async with _mcp.session_manager.run():
        yield


app = FastAPI(title="zip-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap_settings = ApiSettings()
_origins = cors_list(_bootstrap_settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _merge_repo_root(settings: ApiSettings, query_repo: str | None) -> str | None:
    if query_repo and query_repo.strip():
        return query_repo.strip()
    return settings.repo_root


async def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    chunk_size = 1024 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        data += chunk
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Upload exceeds ZIP_TO_MD_MAX_UPLOAD_MB",
            )
    return bytes(data)


@app.post("/convert/sync")
async def convert_sync(
    request: Request,
    file: UploadFile = File(...),
    enable_office: bool = True,
    image_ocr: bool = False,
    pdf_ocr: bool = False,
    max_bytes: int = 512_000,
    expand_nested_zips: bool = True,
    max_nested_zip_depth: int = 16,
    repo_root: str | None = None,
    use_image_to_md: bool = True,
    image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES,
    image_to_md_strategy: str = "best",
    image_to_md_title: str = "",
) -> Response:
    settings: ApiSettings = request.app.state.settings
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, detail="Expected a .zip file upload (multipart field 'file')")
    max_u = settings.max_upload_mb * 1024 * 1024
    max_sync = settings.max_sync_upload_mb * 1024 * 1024
    body = await _read_upload_limited(file, max_u)
    if len(body) > max_sync:
        raise HTTPException(
            status_code=409,
            detail="File too large for synchronous conversion; use POST /convert/jobs",
        )
    rr = _merge_repo_root(settings, repo_root)
    opts = convert_options_from_query(
        enable_office=enable_office,
        image_ocr=image_ocr,
        pdf_ocr=pdf_ocr,
        max_bytes=max_bytes,
        expand_nested_zips=expand_nested_zips,
        max_nested_zip_depth=max_nested_zip_depth,
        repo_root=rr,
        use_image_to_md=use_image_to_md,
        image_to_md_engines=image_to_md_engines,
        image_to_md_strategy=image_to_md_strategy,
        image_to_md_title=image_to_md_title,
    )
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        tf.write(body)
        tmp_in = Path(tf.name)
    try:
        zbytes = build_artifact_zip_bytes(tmp_in, opts)
    finally:
        tmp_in.unlink(missing_ok=True)
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="artifact.zip"'},
    )


@app.post("/convert/jobs")
async def convert_jobs(
    request: Request,
    file: UploadFile = File(...),
    enable_office: bool = True,
    image_ocr: bool = False,
    pdf_ocr: bool = False,
    max_bytes: int = 512_000,
    expand_nested_zips: bool = True,
    max_nested_zip_depth: int = 16,
    repo_root: str | None = None,
    use_image_to_md: bool = True,
    image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES,
    image_to_md_strategy: str = "best",
    image_to_md_title: str = "",
) -> dict:
    settings: ApiSettings = request.app.state.settings
    store: JobStore = request.app.state.job_store
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, detail="Expected a .zip file upload (multipart field 'file')")
    max_u = settings.max_upload_mb * 1024 * 1024
    body = await _read_upload_limited(file, max_u)
    rr = _merge_repo_root(settings, repo_root)
    opts = convert_options_from_query(
        enable_office=enable_office,
        image_ocr=image_ocr,
        pdf_ocr=pdf_ocr,
        max_bytes=max_bytes,
        expand_nested_zips=expand_nested_zips,
        max_nested_zip_depth=max_nested_zip_depth,
        repo_root=rr,
        use_image_to_md=use_image_to_md,
        image_to_md_engines=image_to_md_engines,
        image_to_md_strategy=image_to_md_strategy,
        image_to_md_title=image_to_md_title,
    )
    job = store.create_job()
    inp = job.workspace / "upload.zip"
    inp.write_bytes(body)

    def work() -> None:
        zpath = job.workspace / "artifact.zip"
        data = build_artifact_zip_bytes(inp, opts)
        zpath.write_bytes(data)
        job.zip_path = zpath

    store.run_async(job, work)
    return {"job_id": job.job_id, "status": job.status}


@app.get("/convert/jobs/{job_id}")
async def job_status(request: Request, job_id: str) -> dict:
    store: JobStore = request.app.state.job_store
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, detail="Unknown job_id")
    return {
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
    }


@app.get("/convert/jobs/{job_id}/download", response_class=FileResponse)
async def job_download(request: Request, job_id: str) -> FileResponse:
    store: JobStore = request.app.state.job_store
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, detail="Unknown job_id")
    if job.status != "done" or not job.zip_path or not job.zip_path.is_file():
        raise HTTPException(400, detail="Job is not ready for download")
    path = job.zip_path
    task = BackgroundTask(store.remove_after_download, job)
    return FileResponse(
        path,
        media_type="application/zip",
        filename="artifact.zip",
        background=task,
    )
