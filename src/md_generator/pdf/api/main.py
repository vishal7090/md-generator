"""FastAPI: REST, Swagger, artifact ZIP, Streamable HTTP MCP at /mcp."""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import shutil
import tempfile

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from md_generator.pdf.api import settings
from md_generator.pdf.api.mcp_server import mcp
from md_generator.pdf.api.zip_bundle import zip_artifact_dir
from md_generator.pdf.pdf_extract import ConvertOptions, convert_pdf_to_artifact_dir


async def _read_pdf_bytes(upload: UploadFile, limit_mb: int) -> bytes:
    limit = max(0, limit_mb) * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        block = await upload.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail="Upload exceeds PDF_TO_MD_MAX_UPLOAD_MB",
            )
        chunks.append(block)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    return data


def _is_pdf_name(name: Optional[str]) -> bool:
    if not name:
        return True
    return name.lower().endswith(".pdf")


class JobRecord:
    __slots__ = ("status", "error", "created_at", "workdir", "zip_path")

    def __init__(self) -> None:
        self.status = "queued"
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.workdir: Optional[Path] = None
        self.zip_path: Optional[Path] = None


_jobs_lock = threading.Lock()
_jobs: Dict[str, JobRecord] = {}
_sweeper_stop = threading.Event()


def _sweep_jobs() -> None:
    ttl = settings.job_ttl_seconds()
    now = time.time()
    with _jobs_lock:
        to_del: list[tuple[str, Optional[Path]]] = []
        for jid, job in _jobs.items():
            if now - job.created_at <= ttl:
                continue
            to_del.append((jid, job.workdir))
        for jid, wd in to_del:
            _jobs.pop(jid, None)
            if wd and Path(wd).exists():
                shutil.rmtree(wd, ignore_errors=True)


def _sweeper_loop() -> None:
    while not _sweeper_stop.wait(60.0):
        try:
            _sweep_jobs()
        except Exception:
            pass


def _run_job(job_id: str, pdf_bytes: bytes, ocr: bool, ocr_min_chars: int) -> None:
    root: Optional[Path] = None
    try:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            return
        with _jobs_lock:
            job.status = "running"
        base = settings.temp_dir()
        root = Path(
            tempfile.mkdtemp(prefix=f"pdf-to-md-job-{job_id}-", dir=base)
        )
        pdf_path = root / "upload.pdf"
        pdf_path.write_bytes(pdf_bytes)
        bundle = root / "bundle"
        opts = ConvertOptions(
            use_ocr=ocr,
            ocr_min_chars=ocr_min_chars,
            verbose=False,
        )
        convert_pdf_to_artifact_dir(pdf_path, bundle, opts)
        zpath = root / "artifact.zip"
        zip_artifact_dir(bundle, zpath)
        with _jobs_lock:
            j = _jobs.get(job_id)
            if j is None:
                shutil.rmtree(root, ignore_errors=True)
                return
            j.workdir = root
            j.zip_path = zpath
            j.status = "done"
            root = None
    except Exception as e:
        with _jobs_lock:
            j = _jobs.get(job_id)
            if j is not None:
                j.status = "failed"
                j.error = str(e)
        if root is not None and Path(root).exists():
            shutil.rmtree(root, ignore_errors=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _sweeper_stop.clear()
    th = threading.Thread(target=_sweeper_loop, daemon=True)
    th.start()
    yield
    _sweeper_stop.set()
    th.join(timeout=2.0)


app = FastAPI(title="pdf-to-md", lifespan=lifespan)
_origins = settings.cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/convert/sync")
async def convert_sync(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ocr: bool = False,
    ocr_min_chars: int = 40,
) -> FileResponse:
    if not _is_pdf_name(file.filename):
        raise HTTPException(status_code=400, detail="expected a .pdf file")
    data = await _read_pdf_bytes(file, settings.max_upload_mb())
    sync_limit = settings.max_sync_upload_mb() * 1024 * 1024
    if len(data) > sync_limit:
        raise HTTPException(
            status_code=409,
            detail="File too large for sync; use POST /convert/jobs",
        )
    base = settings.temp_dir()
    root = Path(tempfile.mkdtemp(prefix="pdf-to-md-sync-", dir=base))
    try:
        pdf_path = root / "upload.pdf"
        pdf_path.write_bytes(data)
        bundle = root / "bundle"
        opts = ConvertOptions(
            use_ocr=ocr,
            ocr_min_chars=ocr_min_chars,
            verbose=False,
        )
        convert_pdf_to_artifact_dir(pdf_path, bundle, opts)
        zpath = root / "artifact.zip"
        zip_artifact_dir(bundle, zpath)
    except HTTPException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

    def _cleanup() -> None:
        shutil.rmtree(root, ignore_errors=True)

    background_tasks.add_task(_cleanup)
    return FileResponse(
        path=str(zpath),
        filename="artifact.zip",
        media_type="application/zip",
    )


@app.post("/convert/jobs")
async def create_job(
    file: UploadFile = File(...),
    ocr: bool = False,
    ocr_min_chars: int = 40,
) -> dict[str, Any]:
    if not _is_pdf_name(file.filename):
        raise HTTPException(status_code=400, detail="expected a .pdf file")
    data = await _read_pdf_bytes(file, settings.max_upload_mb())
    job_id = uuid.uuid4().hex
    rec = JobRecord()
    with _jobs_lock:
        _jobs[job_id] = rec
    threading.Thread(
        target=_run_job,
        args=(job_id, data, ocr, ocr_min_chars),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/convert/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
    }


@app.get("/convert/jobs/{job_id}/download")
def job_download(job_id: str, background_tasks: BackgroundTasks) -> FileResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="unknown job")
        if job.status != "done" or job.zip_path is None:
            raise HTTPException(status_code=400, detail="job not ready")
        zpath = job.zip_path
        wd = job.workdir
        del _jobs[job_id]

    def _cleanup() -> None:
        if wd and Path(wd).exists():
            shutil.rmtree(wd, ignore_errors=True)

    background_tasks.add_task(_cleanup)
    return FileResponse(
        path=str(zpath),
        filename="artifact.zip",
        media_type="application/zip",
    )


app.mount("/mcp", mcp.streamable_http_app())
