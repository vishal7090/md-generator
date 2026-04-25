from __future__ import annotations

import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from md_generator.openapi.api.schemas import OpenapiGenerateOptions, merge_upload_config
from md_generator.openapi.api.settings import OpenapiToMdSettings, cors_list
from md_generator.openapi.core.zip_export import build_markdown_zip_bytes
from md_generator.openapi.mcp.server import build_mcp_stack

_mcp, _mcp_http = build_mcp_stack(mount_under_fastapi=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = OpenapiToMdSettings()
    app.state.settings = settings
    async with _mcp.session_manager.run():
        yield


app = FastAPI(title="openapi-to-md", lifespan=lifespan)
app.mount("/mcp", _mcp_http)

_bootstrap = OpenapiToMdSettings()
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


@app.post("/openapi-to-md/generate")
async def api_generate(
    request: Request,
    file: UploadFile = File(...),
    options_json: str | None = Form(default=None),
) -> Response:
    settings: OpenapiToMdSettings = request.app.state.settings
    options: OpenapiGenerateOptions | None = None
    if options_json:
        try:
            options = OpenapiGenerateOptions.model_validate(json.loads(options_json))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid options JSON: {e}") from e
    suffix = Path(file.filename or "openapi.yaml").suffix.lower()
    if suffix not in (".yaml", ".yml", ".json"):
        suffix = ".yaml"
    raw = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        cfg = merge_upload_config(tmp_path, options)
        try:
            data = build_markdown_zip_bytes(cfg)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        max_b = settings.max_sync_zip_mb * 1024 * 1024
        if len(data) > max_b:
            raise HTTPException(
                status_code=413,
                detail=f"ZIP exceeds OPENAPI_TO_MD_MAX_SYNC_ZIP_MB ({settings.max_sync_zip_mb})",
            )
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="api-metadata.zip"'},
        )
    finally:
        tmp_path.unlink(missing_ok=True)
