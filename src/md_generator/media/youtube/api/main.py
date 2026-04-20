"""FastAPI: JSON URL conversion (sync + jobs) and Streamable HTTP MCP at ``/mcp``."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from md_generator.media.job_store import MediaJobStore
from md_generator.media.youtube.api.mcp_setup import build_mcp_stack
from md_generator.media.youtube.api.settings import YouTubeApiSettings, cors_list
from md_generator.media.youtube.metadata import extract_video_id
from md_generator.media.youtube.service import YouTubeError, YouTubeToMarkdownService


class YouTubeConvertRequest(BaseModel):
    url: str = Field(..., min_length=1, description="YouTube watch, youtu.be, shorts, or embed URL")
    title: str | None = None
    transcript_languages: list[str] | None = None
    enable_audio_fallback: bool = True
    whisper_model: str = "base"
    language: str | None = Field(default=None, description="Whisper language if audio fallback runs")


def _validate_url(url: str) -> str:
    u = url.strip()
    if extract_video_id(u) is None:
        raise HTTPException(status_code=400, detail="Invalid or unsupported YouTube URL")
    return u


def create_app() -> FastAPI:
    mcp, mcp_http = build_mcp_stack(mount_under_fastapi=True)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings = YouTubeApiSettings()
        base = Path(settings.temp_dir) if settings.temp_dir else None
        store = MediaJobStore(base, settings.job_ttl_seconds)
        store.start_sweeper()
        application.state.settings = settings
        application.state.job_store = store
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="youtube-to-md", lifespan=lifespan)
    app.mount("/mcp", mcp_http)

    _bootstrap = YouTubeApiSettings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_list(_bootstrap),
        allow_credentials="*" not in cors_list(_bootstrap),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/convert/sync")
    async def convert_sync(body: YouTubeConvertRequest) -> Response:
        url = _validate_url(body.url)
        with tempfile.TemporaryDirectory(prefix="yt-sync-") as td_name:
            out = Path(td_name) / "transcript.md"
            svc = YouTubeToMarkdownService(whisper_model=body.whisper_model, whisper_language=body.language)
            try:
                svc.write_markdown(
                    url,
                    out,
                    title=body.title,
                    transcript_languages=body.transcript_languages,
                    enable_audio_fallback=body.enable_audio_fallback,
                )
            except YouTubeError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            md = out.read_text(encoding="utf-8")
        return Response(
            content=md.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="transcript.md"'},
        )

    @app.post("/convert/jobs")
    async def convert_jobs(request: Request, body: YouTubeConvertRequest) -> dict:
        url = _validate_url(body.url)
        store: MediaJobStore = request.app.state.job_store
        job = store.create_job()
        out = job.workspace / "transcript.md"

        def work() -> None:
            svc = YouTubeToMarkdownService(whisper_model=body.whisper_model, whisper_language=body.language)
            svc.write_markdown(
                url,
                out,
                title=body.title,
                transcript_languages=body.transcript_languages,
                enable_audio_fallback=body.enable_audio_fallback,
            )
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
