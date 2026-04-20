from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from starlette.background import BackgroundTask

from md_generator.playwright.api.convert_runner import build_artifact_zip_bytes
from md_generator.playwright.api.jobs import JobStore
from md_generator.playwright.api.mcp_setup import build_mcp_stack
from md_generator.playwright.api.settings import PlaywrightApiSettings, cors_list
from md_generator.playwright.options import PlaywrightOptions, WaitUntil

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


def _is_http_url(s: str) -> bool:
    p = urlparse(s.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


WaitUntilField = Literal["load", "domcontentloaded", "commit", "networkidle"]


class ConvertJsonBody(BaseModel):
    url: str | None = None
    urls: list[str] | None = None
    navigation_timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    wait_selector: str | None = None
    wait_until: WaitUntilField = "networkidle"
    max_scroll_rounds: int = Field(default=12, ge=0, le=100)
    scroll_pause_ms: float = Field(default=400.0, ge=0.0, le=10_000.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_backoff_seconds: float = Field(default=1.5, ge=0.1, le=60.0)
    headless: bool = True
    use_readability: bool = True
    chunk_markdown: bool = True
    max_chunk_tokens: int = Field(default=900, ge=100, le=8000)
    chars_per_token: int = Field(default=4, ge=1, le=16)
    max_images: int = Field(default=40, ge=0, le=200)
    max_image_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    asset_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)

    @model_validator(mode="after")
    def check_source(self) -> ConvertJsonBody:
        has_url = self.url is not None and bool(self.url.strip())
        has_urls = self.urls is not None and len(self.urls) > 0
        if not has_url and not has_urls:
            raise ValueError("Provide url or urls")
        if has_url and has_urls:
            raise ValueError("Provide only one of url or urls")
        if self.urls:
            for u in self.urls:
                if not _is_http_url(u):
                    raise ValueError(f"Invalid URL: {u!r}")
        if self.url and not _is_http_url(self.url):
            raise ValueError("Invalid url")
        return self


def _merged_options(
    body: ConvertJsonBody,
    *,
    navigation_timeout_seconds: float | None = None,
    wait_selector: str | None = None,
    wait_until: WaitUntil | None = None,
    max_scroll_rounds: int | None = None,
    scroll_pause_ms: float | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
    headless: bool | None = None,
    use_readability: bool | None = None,
    chunk_markdown: bool | None = None,
    max_chunk_tokens: int | None = None,
    chars_per_token: int | None = None,
    max_images: int | None = None,
    max_image_bytes: int | None = None,
    asset_timeout_seconds: float | None = None,
) -> PlaywrightOptions:
    wu: WaitUntil = wait_until if wait_until is not None else body.wait_until  # type: ignore[assignment]
    nav_s = (
        navigation_timeout_seconds
        if navigation_timeout_seconds is not None
        else body.navigation_timeout_seconds
    )
    return PlaywrightOptions(
        navigation_timeout_ms=nav_s * 1000.0,
        wait_selector=wait_selector if wait_selector is not None else body.wait_selector,
        wait_until=wu,
        max_scroll_rounds=max_scroll_rounds if max_scroll_rounds is not None else body.max_scroll_rounds,
        scroll_pause_ms=scroll_pause_ms if scroll_pause_ms is not None else body.scroll_pause_ms,
        max_retries=max_retries if max_retries is not None else body.max_retries,
        retry_backoff_seconds=retry_backoff_seconds
        if retry_backoff_seconds is not None
        else body.retry_backoff_seconds,
        headless=headless if headless is not None else body.headless,
        use_readability=use_readability if use_readability is not None else body.use_readability,
        chunk_markdown=chunk_markdown if chunk_markdown is not None else body.chunk_markdown,
        max_chunk_tokens=max_chunk_tokens if max_chunk_tokens is not None else body.max_chunk_tokens,
        chars_per_token=chars_per_token if chars_per_token is not None else body.chars_per_token,
        max_images=max_images if max_images is not None else body.max_images,
        max_image_bytes=max_image_bytes if max_image_bytes is not None else body.max_image_bytes,
        asset_timeout_seconds=asset_timeout_seconds
        if asset_timeout_seconds is not None
        else body.asset_timeout_seconds,
        verbose=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = PlaywrightApiSettings()
    base = Path(settings.temp_dir) if settings.temp_dir else None
    store = JobStore(base, settings.job_ttl_seconds)
    store.start_sweeper()
    app.state.settings = settings
    app.state.job_store = store
    async with _mcp.session_manager.run():
        yield


app = FastAPI(title="playwright-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap_settings = PlaywrightApiSettings()
_origins = cors_list(_bootstrap_settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _count_targets(body: ConvertJsonBody) -> int:
    if body.urls:
        return len(body.urls)
    return 1


def _sync_allowed(settings: PlaywrightApiSettings, body: ConvertJsonBody) -> bool:
    return _count_targets(body) <= settings.max_sync_urls


@app.post("/convert/sync")
async def convert_sync(
    request: Request,
    body: ConvertJsonBody,
    navigation_timeout_seconds: float | None = None,
    wait_selector: str | None = None,
    wait_until: WaitUntilField | None = None,
    max_scroll_rounds: int | None = None,
    scroll_pause_ms: float | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
    headless: bool | None = None,
    use_readability: bool | None = None,
    chunk_markdown: bool | None = None,
    max_chunk_tokens: int | None = None,
    chars_per_token: int | None = None,
    max_images: int | None = None,
    max_image_bytes: int | None = None,
    asset_timeout_seconds: float | None = None,
) -> Response:
    settings: PlaywrightApiSettings = request.app.state.settings
    if _count_targets(body) > settings.max_job_urls:
        raise HTTPException(400, detail=f"At most {settings.max_job_urls} URLs per request")

    opts = _merged_options(
        body,
        navigation_timeout_seconds=navigation_timeout_seconds,
        wait_selector=wait_selector,
        wait_until=wait_until,
        max_scroll_rounds=max_scroll_rounds,
        scroll_pause_ms=scroll_pause_ms,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        headless=headless,
        use_readability=use_readability,
        chunk_markdown=chunk_markdown,
        max_chunk_tokens=max_chunk_tokens,
        chars_per_token=chars_per_token,
        max_images=max_images,
        max_image_bytes=max_image_bytes,
        asset_timeout_seconds=asset_timeout_seconds,
    )
    if not _sync_allowed(settings, body):
        raise HTTPException(
            status_code=409,
            detail="Too many URLs for sync; use POST /convert/jobs",
        )

    url_arg = body.url.strip() if body.url else None
    urls_arg = body.urls
    zbytes = build_artifact_zip_bytes(url=url_arg, urls=urls_arg, options=opts)
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="artifact.zip"'},
    )


@app.post("/convert/jobs")
async def convert_jobs(
    request: Request,
    body: ConvertJsonBody,
    navigation_timeout_seconds: float | None = None,
    wait_selector: str | None = None,
    wait_until: WaitUntilField | None = None,
    max_scroll_rounds: int | None = None,
    scroll_pause_ms: float | None = None,
    max_retries: int | None = None,
    retry_backoff_seconds: float | None = None,
    headless: bool | None = None,
    use_readability: bool | None = None,
    chunk_markdown: bool | None = None,
    max_chunk_tokens: int | None = None,
    chars_per_token: int | None = None,
    max_images: int | None = None,
    max_image_bytes: int | None = None,
    asset_timeout_seconds: float | None = None,
) -> dict:
    settings: PlaywrightApiSettings = request.app.state.settings
    store: JobStore = request.app.state.job_store
    if _count_targets(body) > settings.max_job_urls:
        raise HTTPException(400, detail=f"At most {settings.max_job_urls} URLs per request")

    opts = _merged_options(
        body,
        navigation_timeout_seconds=navigation_timeout_seconds,
        wait_selector=wait_selector,
        wait_until=wait_until,
        max_scroll_rounds=max_scroll_rounds,
        scroll_pause_ms=scroll_pause_ms,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        headless=headless,
        use_readability=use_readability,
        chunk_markdown=chunk_markdown,
        max_chunk_tokens=max_chunk_tokens,
        chars_per_token=chars_per_token,
        max_images=max_images,
        max_image_bytes=max_image_bytes,
        asset_timeout_seconds=asset_timeout_seconds,
    )
    job = store.create_job()
    url_arg = body.url.strip() if body.url else None
    urls_arg = body.urls

    def work() -> None:
        zbytes = build_artifact_zip_bytes(url=url_arg, urls=urls_arg, options=opts)
        zpath = job.workspace / "artifact.zip"
        zpath.write_bytes(zbytes)
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
