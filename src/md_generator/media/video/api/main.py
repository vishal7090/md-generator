"""FastAPI: REST (sync + jobs) and Streamable HTTP MCP at ``/mcp``."""

from __future__ import annotations

import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from starlette.background import BackgroundTask

from md_generator.media.job_store import MediaJobStore
from md_generator.media.video.api.mcp_setup import build_mcp_stack
from md_generator.media.video.api.settings import VideoApiSettings, cors_list
from md_generator.media.video.service import VideoToMarkdownService

_VIDEO_EXTS = frozenset(
    {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg", ".ogv"}
)


def _safe_upload_name(name: str | None) -> str:
    raw = (name or "upload.bin").strip()
    return re.sub(r"[^\w.\-]+", "_", raw) or "upload.bin"


def _require_video_ext(path: Path) -> None:
    if path.suffix.lower() not in _VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video extension (allowed: {', '.join(sorted(_VIDEO_EXTS))})",
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
                detail="Upload exceeds MD_VIDEO_MAX_UPLOAD_MB",
            )
    return bytes(data)


def create_app() -> FastAPI:
    """Build a new app (new MCP session manager) — use with uvicorn ``factory=True`` and in tests."""
    mcp, mcp_http = build_mcp_stack(mount_under_fastapi=True)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings = VideoApiSettings()
        base = Path(settings.temp_dir) if settings.temp_dir else None
        store = MediaJobStore(base, settings.job_ttl_seconds)
        store.start_sweeper()
        application.state.settings = settings
        application.state.job_store = store
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="video-to-md", lifespan=lifespan)
    app.mount("/mcp", mcp_http)

    _bootstrap = VideoApiSettings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_list(_bootstrap),
        allow_credentials="*" not in cors_list(_bootstrap),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/convert/sync")
    async def convert_sync(
        request: Request,
        file: UploadFile = File(...),
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> Response:
        settings: VideoApiSettings = request.app.state.settings
        max_u = settings.max_upload_mb * 1024 * 1024
        max_sync = settings.max_sync_upload_mb * 1024 * 1024
        body = await _read_upload_limited(file, max_u)
        if len(body) > max_sync:
            raise HTTPException(
                status_code=409,
                detail="File too large for synchronous conversion; use POST /convert/jobs",
            )
        safe = _safe_upload_name(file.filename)
        _require_video_ext(Path(safe))

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / safe
            src.write_bytes(body)
            out = Path(td) / "transcript.md"
            svc = VideoToMarkdownService(whisper_model=whisper_model, language=language)
            svc.write_markdown(src, out, title=title)
            md = out.read_text(encoding="utf-8")
        return Response(
            content=md.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="transcript.md"'},
        )

    @app.post("/convert/jobs")
    async def convert_jobs(
        request: Request,
        file: UploadFile = File(...),
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> dict:
        settings: VideoApiSettings = request.app.state.settings
        store: MediaJobStore = request.app.state.job_store
        max_u = settings.max_upload_mb * 1024 * 1024
        body = await _read_upload_limited(file, max_u)
        safe = _safe_upload_name(file.filename)
        _require_video_ext(Path(safe))

        job = store.create_job()
        src = job.workspace / safe
        src.write_bytes(body)
        out = job.workspace / "transcript.md"

        def work() -> None:
            svc = VideoToMarkdownService(whisper_model=whisper_model, language=language)
            svc.write_markdown(src, out, title=title)
            job.result_path = out

        store.run_async(job, work)
        return {"job_id": job.job_id, "status": job.status}

    @app.get("/convert/jobs/{job_id}")
    async def job_status(request: Request, job_id: str) -> dict:
        store: MediaJobStore = request.app.state.job_store
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
        store: MediaJobStore = request.app.state.job_store
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, detail="Unknown job_id")
        if job.status != "done" or not job.result_path or not job.result_path.is_file():
            raise HTTPException(400, detail="Job is not ready for download")
        path = job.result_path
        task = BackgroundTask(store.remove_after_download, job)
        return FileResponse(
            path,
            media_type="text/markdown; charset=utf-8",
            filename="transcript.md",
            background=task,
        )

    return app


app = create_app()
