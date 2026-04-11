from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from api.convert_runner import build_artifact_zip_bytes
from api.jobs import JobStore
from api.mcp_setup import build_mcp_stack
from api.query_options import convert_options_from_query
from api.settings import ApiSettings, cors_list

# Mounted MCP: streamable_http_path="/". Run session_manager.run() in our lifespan so Streamable HTTP works
# (Starlette sub-app lifespan is not invoked when mounted on FastAPI by default).
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


app = FastAPI(title="ppt-to-md", lifespan=lifespan)
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
                detail="Upload exceeds PPT_TO_MD_MAX_UPLOAD_MB",
            )
    return bytes(data)


@app.post("/convert/sync")
async def convert_sync(
    request: Request,
    file: UploadFile = File(...),
    extract_embedded_deep: bool = True,
    max_unpack_depth: int = 2,
    emit_extracted_txt_md: bool = True,
    extracted_pdf_ocr: bool = True,
    extracted_pdf_ocr_min_chars: int = 50,
    chart_data: bool = True,
    chart_image: bool = True,
    table_csv: bool = True,
    extracted_docx_md: bool = True,
    extracted_pdf_md: bool = True,
    extracted_xlsx_md: bool = True,
) -> Response:
    settings: ApiSettings = request.app.state.settings
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(400, detail="Expected a .pptx file upload (multipart field 'file')")
    max_u = settings.max_upload_mb * 1024 * 1024
    max_sync = settings.max_sync_upload_mb * 1024 * 1024
    body = await _read_upload_limited(file, max_u)
    if len(body) > max_sync:
        raise HTTPException(
            status_code=409,
            detail="File too large for synchronous conversion; use POST /convert/jobs",
        )
    opts = convert_options_from_query(
        extract_embedded_deep=extract_embedded_deep,
        max_unpack_depth=max_unpack_depth,
        emit_extracted_txt_md=emit_extracted_txt_md,
        extracted_pdf_ocr=extracted_pdf_ocr,
        extracted_pdf_ocr_min_chars=extracted_pdf_ocr_min_chars,
        chart_data=chart_data,
        chart_image=chart_image,
        table_csv=table_csv,
        extracted_docx_md=extracted_docx_md,
        extracted_pdf_md=extracted_pdf_md,
        extracted_xlsx_md=extracted_xlsx_md,
    )
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tf:
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
    extract_embedded_deep: bool = True,
    max_unpack_depth: int = 2,
    emit_extracted_txt_md: bool = True,
    extracted_pdf_ocr: bool = True,
    extracted_pdf_ocr_min_chars: int = 50,
    chart_data: bool = True,
    chart_image: bool = True,
    table_csv: bool = True,
    extracted_docx_md: bool = True,
    extracted_pdf_md: bool = True,
    extracted_xlsx_md: bool = True,
) -> dict:
    settings: ApiSettings = request.app.state.settings
    store: JobStore = request.app.state.job_store
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(400, detail="Expected a .pptx file upload (multipart field 'file')")
    max_u = settings.max_upload_mb * 1024 * 1024
    body = await _read_upload_limited(file, max_u)
    opts = convert_options_from_query(
        extract_embedded_deep=extract_embedded_deep,
        max_unpack_depth=max_unpack_depth,
        emit_extracted_txt_md=emit_extracted_txt_md,
        extracted_pdf_ocr=extracted_pdf_ocr,
        extracted_pdf_ocr_min_chars=extracted_pdf_ocr_min_chars,
        chart_data=chart_data,
        chart_image=chart_image,
        table_csv=table_csv,
        extracted_docx_md=extracted_docx_md,
        extracted_pdf_md=extracted_pdf_md,
        extracted_xlsx_md=extracted_xlsx_md,
    )
    job = store.create_job()
    inp = job.workspace / "upload.pptx"
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
