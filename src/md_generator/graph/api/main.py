from __future__ import annotations

import asyncio
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from md_generator.graph.api.schemas import GraphToMdRunBody
from md_generator.graph.api.settings import GraphApiSettings, cors_list, sqlite_path_resolved
from md_generator.graph.core.job_manager import GraphJobManager
from md_generator.graph.core.zip_export import build_markdown_zip_bytes
from md_generator.graph.mcp.server import build_mcp_stack
from md_generator.graph.mcp.sse import format_sse

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = GraphApiSettings()
    ws = Path(settings.job_workspace_root) if settings.job_workspace_root else None
    jobs = GraphJobManager(sqlite_path=sqlite_path_resolved(settings), workspace_root=ws)
    app.state.settings = settings
    app.state.jobs = jobs
    async with _mcp.session_manager.run():
        yield
    jobs.close()


app = FastAPI(title="graph-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap = GraphApiSettings()
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


@app.post("/graph-to-md/run")
async def graph_run_sync(request: Request, body: GraphToMdRunBody) -> Response:
    settings: GraphApiSettings = request.app.state.settings
    cfg = body.to_run_config()
    try:
        data = build_markdown_zip_bytes(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    max_b = settings.max_sync_zip_mb * 1024 * 1024
    if len(data) > max_b:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP exceeds GRAPH_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb}); use POST /graph-to-md/job",
        )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="graph-metadata.zip"'},
    )


@app.post("/graph-to-md/job")
async def graph_job_create(request: Request, body: GraphToMdRunBody) -> dict[str, str]:
    jobs: GraphJobManager = request.app.state.jobs
    cfg = body.to_run_config()
    try:
        rec = jobs.create_job(cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    jobs.run_job_thread(rec.job_id)
    return {"job_id": rec.job_id}


@app.get("/graph-to-md/job/{job_id}")
async def graph_job_status(request: Request, job_id: str) -> dict:
    jobs: GraphJobManager = request.app.state.jobs
    rec = jobs.get(job_id)
    if not rec:
        raise HTTPException(404, detail="Unknown job_id")
    return rec.to_api_dict()


@app.get("/graph-to-md/job/{job_id}/download")
async def graph_job_download(request: Request, job_id: str) -> FileResponse:
    jobs: GraphJobManager = request.app.state.jobs
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
        filename="graph-metadata.zip",
        background=task,
    )


@app.get("/graph-to-md/job/{job_id}/events")
async def graph_job_events(request: Request, job_id: str) -> StreamingResponse:
    jobs: GraphJobManager = request.app.state.jobs

    async def gen():
        rec = jobs.get(job_id)
        if not rec:
            yield format_sse("job_failed", {"job_id": job_id, "error": "unknown job_id"}).encode("utf-8")
            return
        yield format_sse("graph_extraction_started", {"job_id": job_id}).encode("utf-8")
        last_progress = -1
        last_current = ""
        while True:
            rec = jobs.get(job_id)
            if not rec:
                yield format_sse("job_failed", {"job_id": job_id, "error": "job disappeared"}).encode("utf-8")
                return
            if rec.progress != last_progress or (rec.current and rec.current != last_current):
                last_progress = rec.progress
                last_current = rec.current or ""
                ev = last_current if last_current else "progress_update"
                yield format_sse(
                    ev,
                    {"job_id": job_id, "progress": rec.progress, "current": rec.current},
                ).encode("utf-8")
            if rec.status == "COMPLETED":
                yield format_sse(
                    "graph_completed",
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


@app.get("/graph-to-md/job/{job_id}/stream")
async def graph_job_stream(request: Request, job_id: str) -> StreamingResponse:
    jobs: GraphJobManager = request.app.state.jobs

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
