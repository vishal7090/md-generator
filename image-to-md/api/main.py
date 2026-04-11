"""FastAPI: REST, artifact ZIP, Streamable HTTP MCP at /mcp."""

from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from api import settings
from api.mcp_server import mcp
from api.query_options import convert_options_from_query
from api.staging import stage_upload_bytes
from api.zip_bundle import zip_artifact_dir
from src.convert_impl import convert_images_recursive
from src.io_util import is_image_path, iter_image_paths_recursive


async def _read_upload_bytes(upload: UploadFile, limit_mb: int) -> bytes:
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
                detail="Upload exceeds IMAGE_TO_MD_MAX_UPLOAD_MB",
            )
        chunks.append(block)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    return data


def _image_count(staged: Path) -> int:
    if staged.is_file():
        return 1 if is_image_path(staged) else 0
    return len(iter_image_paths_recursive(staged))


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


def _run_convert_job(job_id: str, data: bytes, filename: Optional[str], opts_kwargs: dict[str, Any]) -> None:
    root: Optional[Path] = None
    try:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            return
        with _jobs_lock:
            job.status = "running"
        base = settings.temp_dir()
        root = Path(tempfile.mkdtemp(prefix=f"image-to-md-job-{job_id}-", dir=base))
        staged = stage_upload_bytes(root / "stage", filename, data)
        if _image_count(staged) == 0:
            raise ValueError("No supported images found in upload (use .png/.jpg/… or a .zip of images)")

        opts = convert_options_from_query(**opts_kwargs)
        bundle = root / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        convert_images_recursive(staged, bundle / "document.md", opts)
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


app = FastAPI(title="image-to-md", lifespan=lifespan)
_origins = settings.cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _query_opts(
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> dict[str, Any]:
    if strategy not in ("compare", "best"):
        raise HTTPException(status_code=400, detail="strategy must be compare or best")
    return {
        "engines": engines,
        "strategy": strategy,
        "title": title,
        "lang": lang,
        "paddle_lang": paddle_lang,
        "paddle_no_angle_cls": paddle_no_angle_cls,
        "easy_lang": easy_lang,
    }


@app.post("/convert/sync")
async def convert_sync(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> FileResponse:
    data = await _read_upload_bytes(file, settings.max_upload_mb())
    sync_limit = settings.max_sync_upload_mb() * 1024 * 1024
    if len(data) > sync_limit:
        raise HTTPException(
            status_code=409,
            detail="File too large for sync; use POST /convert/jobs",
        )
    base = settings.temp_dir()
    root = Path(tempfile.mkdtemp(prefix="image-to-md-sync-", dir=base))
    try:
        staged = stage_upload_bytes(root / "stage", file.filename, data)
        if _image_count(staged) == 0:
            raise HTTPException(
                status_code=400,
                detail="No supported images in upload (use an image file or .zip of images)",
            )
        opts = convert_options_from_query(**_query_opts(
            engines=engines,
            strategy=strategy,
            title=title,
            lang=lang,
            paddle_lang=paddle_lang,
            paddle_no_angle_cls=paddle_no_angle_cls,
            easy_lang=easy_lang,
        ))
        bundle = root / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        convert_images_recursive(staged, bundle / "document.md", opts)
        zpath = root / "artifact.zip"
        zip_artifact_dir(bundle, zpath)
    except HTTPException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except ValueError as e:
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> dict[str, Any]:
    data = await _read_upload_bytes(file, settings.max_upload_mb())
    job_id = uuid.uuid4().hex
    rec = JobRecord()
    with _jobs_lock:
        _jobs[job_id] = rec
    opts_kw = _query_opts(
        engines=engines,
        strategy=strategy,
        title=title,
        lang=lang,
        paddle_lang=paddle_lang,
        paddle_no_angle_cls=paddle_no_angle_cls,
        easy_lang=easy_lang,
    )
    threading.Thread(
        target=_run_convert_job,
        args=(job_id, data, file.filename, opts_kw),
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
