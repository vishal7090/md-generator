from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from starlette.background import BackgroundTask

from md_generator.url.api.convert_runner import build_artifact_zip_bytes, zip_directory
from md_generator.url.api.jobs import JobStore
from md_generator.url.api.mcp_setup import build_mcp_stack
from md_generator.url.api.settings import ApiSettings, cors_list
from md_generator.url.convert_impl import convert_url_job
from md_generator.url.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


def _is_http_url(s: str) -> bool:
    p = urlparse(s.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


class ConvertJsonBody(BaseModel):
    url: str | None = None
    urls: list[str] | None = None
    crawl: bool = False
    async_crawl: bool = False
    crawl_max_concurrency: int = Field(default=4, ge=1, le=32)
    max_depth: int = Field(default=2, ge=0, le=20)
    max_pages: int = Field(default=30, ge=1, le=500)
    crawl_delay_seconds: float = Field(default=0.5, ge=0.0, le=60.0)
    obey_robots: bool = True
    include_subdomains: bool = True
    table_csv: bool = True
    download_linked_files: bool = True
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    max_response_mb: float = Field(default=10.0, ge=0.5, le=100.0)
    convert_downloaded_assets: bool = True
    convert_downloaded_images: bool = True
    convert_downloaded_image_to_md_engines: str = DEFAULT_IMAGE_TO_MD_ENGINES
    convert_downloaded_image_to_md_strategy: str = "best"
    convert_downloaded_image_to_md_title: str = ""
    post_convert_pdf_ocr: bool = False
    post_convert_pdf_ocr_min_chars: int = Field(default=40, ge=1, le=500)
    post_convert_ppt_embedded_deep: bool = True
    max_linked_files: int = Field(default=40, ge=1, le=500)
    max_downloaded_images: int = Field(default=50, ge=1, le=200)

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
    crawl: bool | None = None,
    async_crawl: bool | None = None,
    crawl_max_concurrency: int | None = None,
    max_depth: int | None = None,
    max_pages: int | None = None,
    crawl_delay_seconds: float | None = None,
    obey_robots: bool | None = None,
    include_subdomains: bool | None = None,
    table_csv: bool | None = None,
    download_linked_files: bool | None = None,
    timeout_seconds: float | None = None,
    max_response_bytes: int | None = None,
    convert_downloaded_assets: bool | None = None,
    convert_downloaded_images: bool | None = None,
    convert_downloaded_image_to_md_engines: str | None = None,
    convert_downloaded_image_to_md_strategy: str | None = None,
    convert_downloaded_image_to_md_title: str | None = None,
    post_convert_pdf_ocr: bool | None = None,
    post_convert_pdf_ocr_min_chars: int | None = None,
    post_convert_ppt_embedded_deep: bool | None = None,
    max_linked_files: int | None = None,
    max_downloaded_images: int | None = None,
) -> ConvertOptions:
    return ConvertOptions(
        artifact_layout=True,
        crawl=crawl if crawl is not None else body.crawl,
        async_crawl=async_crawl if async_crawl is not None else body.async_crawl,
        crawl_max_concurrency=crawl_max_concurrency
        if crawl_max_concurrency is not None
        else body.crawl_max_concurrency,
        max_depth=max_depth if max_depth is not None else body.max_depth,
        max_pages=max_pages if max_pages is not None else body.max_pages,
        crawl_delay_seconds=crawl_delay_seconds
        if crawl_delay_seconds is not None
        else body.crawl_delay_seconds,
        obey_robots=obey_robots if obey_robots is not None else body.obey_robots,
        include_subdomains=include_subdomains
        if include_subdomains is not None
        else body.include_subdomains,
        table_csv=table_csv if table_csv is not None else body.table_csv,
        download_linked_files=download_linked_files
        if download_linked_files is not None
        else body.download_linked_files,
        timeout_seconds=timeout_seconds if timeout_seconds is not None else body.timeout_seconds,
        max_response_bytes=max_response_bytes
        if max_response_bytes is not None
        else int(body.max_response_mb * 1024 * 1024),
        convert_downloaded_assets=convert_downloaded_assets
        if convert_downloaded_assets is not None
        else body.convert_downloaded_assets,
        convert_downloaded_images=convert_downloaded_images
        if convert_downloaded_images is not None
        else body.convert_downloaded_images,
        convert_downloaded_image_to_md_engines=(
            body.convert_downloaded_image_to_md_engines
            if convert_downloaded_image_to_md_engines is None
            else (
                convert_downloaded_image_to_md_engines.strip() or DEFAULT_IMAGE_TO_MD_ENGINES
            )
        ),
        convert_downloaded_image_to_md_strategy=(
            convert_downloaded_image_to_md_strategy
            if convert_downloaded_image_to_md_strategy is not None
            else body.convert_downloaded_image_to_md_strategy
        ),
        convert_downloaded_image_to_md_title=(
            convert_downloaded_image_to_md_title
            if convert_downloaded_image_to_md_title is not None
            else body.convert_downloaded_image_to_md_title
        ),
        post_convert_pdf_ocr=post_convert_pdf_ocr
        if post_convert_pdf_ocr is not None
        else body.post_convert_pdf_ocr,
        post_convert_pdf_ocr_min_chars=post_convert_pdf_ocr_min_chars
        if post_convert_pdf_ocr_min_chars is not None
        else body.post_convert_pdf_ocr_min_chars,
        post_convert_ppt_embedded_deep=post_convert_ppt_embedded_deep
        if post_convert_ppt_embedded_deep is not None
        else body.post_convert_ppt_embedded_deep,
        max_linked_files=max_linked_files if max_linked_files is not None else body.max_linked_files,
        max_downloaded_images=max_downloaded_images
        if max_downloaded_images is not None
        else body.max_downloaded_images,
        verbose=False,
    )


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


app = FastAPI(title="url-to-md", lifespan=lifespan)
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


def _count_targets(body: ConvertJsonBody) -> int:
    if body.urls:
        return len(body.urls)
    return 1


def _sync_allowed(settings: ApiSettings, body: ConvertJsonBody, opts: ConvertOptions) -> bool:
    if _count_targets(body) > settings.max_sync_urls:
        return False
    if opts.crawl and opts.max_pages > settings.max_sync_crawl_pages:
        return False
    return True


@app.post("/convert/sync")
async def convert_sync(
    request: Request,
    body: ConvertJsonBody,
    crawl: bool | None = None,
    async_crawl: bool | None = None,
    crawl_max_concurrency: int | None = None,
    max_depth: int | None = None,
    max_pages: int | None = None,
    crawl_delay_seconds: float | None = None,
    obey_robots: bool | None = None,
    include_subdomains: bool | None = None,
    table_csv: bool | None = None,
    download_linked_files: bool | None = None,
    timeout_seconds: float | None = None,
    max_response_bytes: int | None = None,
    convert_downloaded_assets: bool | None = None,
    convert_downloaded_images: bool | None = None,
    convert_downloaded_image_to_md_engines: str | None = None,
    convert_downloaded_image_to_md_strategy: str | None = None,
    convert_downloaded_image_to_md_title: str | None = None,
    post_convert_pdf_ocr: bool | None = None,
    post_convert_pdf_ocr_min_chars: int | None = None,
    post_convert_ppt_embedded_deep: bool | None = None,
    max_linked_files: int | None = None,
    max_downloaded_images: int | None = None,
) -> Response:
    settings: ApiSettings = request.app.state.settings
    if _count_targets(body) > settings.max_job_urls:
        raise HTTPException(400, detail=f"At most {settings.max_job_urls} URLs per request")

    opts = _merged_options(
        body,
        crawl=crawl,
        async_crawl=async_crawl,
        crawl_max_concurrency=crawl_max_concurrency,
        max_depth=max_depth,
        max_pages=max_pages,
        crawl_delay_seconds=crawl_delay_seconds,
        obey_robots=obey_robots,
        include_subdomains=include_subdomains,
        table_csv=table_csv,
        download_linked_files=download_linked_files,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        convert_downloaded_assets=convert_downloaded_assets,
        convert_downloaded_images=convert_downloaded_images,
        convert_downloaded_image_to_md_engines=convert_downloaded_image_to_md_engines,
        convert_downloaded_image_to_md_strategy=convert_downloaded_image_to_md_strategy,
        convert_downloaded_image_to_md_title=convert_downloaded_image_to_md_title,
        post_convert_pdf_ocr=post_convert_pdf_ocr,
        post_convert_pdf_ocr_min_chars=post_convert_pdf_ocr_min_chars,
        post_convert_ppt_embedded_deep=post_convert_ppt_embedded_deep,
        max_linked_files=max_linked_files,
        max_downloaded_images=max_downloaded_images,
    )
    if not _sync_allowed(settings, body, opts):
        raise HTTPException(
            status_code=409,
            detail="Too many URLs or crawl size for sync; use POST /convert/jobs",
        )

    zbytes = build_artifact_zip_bytes(
        url=body.url.strip() if body.url else None,
        urls=body.urls,
        options=opts,
    )
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="artifact.zip"'},
    )


@app.post("/convert/jobs")
async def convert_jobs(
    request: Request,
    body: ConvertJsonBody,
    crawl: bool | None = None,
    async_crawl: bool | None = None,
    crawl_max_concurrency: int | None = None,
    max_depth: int | None = None,
    max_pages: int | None = None,
    crawl_delay_seconds: float | None = None,
    obey_robots: bool | None = None,
    include_subdomains: bool | None = None,
    table_csv: bool | None = None,
    download_linked_files: bool | None = None,
    timeout_seconds: float | None = None,
    max_response_bytes: int | None = None,
    convert_downloaded_assets: bool | None = None,
    convert_downloaded_images: bool | None = None,
    convert_downloaded_image_to_md_engines: str | None = None,
    convert_downloaded_image_to_md_strategy: str | None = None,
    convert_downloaded_image_to_md_title: str | None = None,
    post_convert_pdf_ocr: bool | None = None,
    post_convert_pdf_ocr_min_chars: int | None = None,
    post_convert_ppt_embedded_deep: bool | None = None,
    max_linked_files: int | None = None,
    max_downloaded_images: int | None = None,
) -> dict:
    settings: ApiSettings = request.app.state.settings
    store: JobStore = request.app.state.job_store
    if _count_targets(body) > settings.max_job_urls:
        raise HTTPException(400, detail=f"At most {settings.max_job_urls} URLs per request")

    opts = _merged_options(
        body,
        crawl=crawl,
        async_crawl=async_crawl,
        crawl_max_concurrency=crawl_max_concurrency,
        max_depth=max_depth,
        max_pages=max_pages,
        crawl_delay_seconds=crawl_delay_seconds,
        obey_robots=obey_robots,
        include_subdomains=include_subdomains,
        table_csv=table_csv,
        download_linked_files=download_linked_files,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        convert_downloaded_assets=convert_downloaded_assets,
        convert_downloaded_images=convert_downloaded_images,
        convert_downloaded_image_to_md_engines=convert_downloaded_image_to_md_engines,
        convert_downloaded_image_to_md_strategy=convert_downloaded_image_to_md_strategy,
        convert_downloaded_image_to_md_title=convert_downloaded_image_to_md_title,
        post_convert_pdf_ocr=post_convert_pdf_ocr,
        post_convert_pdf_ocr_min_chars=post_convert_pdf_ocr_min_chars,
        post_convert_ppt_embedded_deep=post_convert_ppt_embedded_deep,
        max_linked_files=max_linked_files,
        max_downloaded_images=max_downloaded_images,
    )
    job = store.create_job()
    artifact = job.workspace / "artifact"
    artifact.mkdir(parents=True, exist_ok=True)

    url_arg = body.url.strip() if body.url else None
    urls_arg = body.urls

    def work() -> None:
        convert_url_job(url_arg, urls_arg, artifact, opts)
        zpath = job.workspace / "artifact.zip"
        zpath.write_bytes(zip_directory(artifact))
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
