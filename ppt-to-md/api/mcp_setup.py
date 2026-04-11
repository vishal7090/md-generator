from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from api.convert_runner import build_artifact_zip_bytes
from api.settings import ApiSettings
from src.options import ConvertOptions


def _decode_base64_pptx(data: str) -> bytes:
    s = data.strip()
    if s.startswith("data:"):
        parts = s.split(",", 1)
        if len(parts) == 2:
            s = parts[1]
    return base64.b64decode(s, validate=False)


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    """
    FastMCP with Streamable HTTP sub-app.
    When mount_under_fastapi=True, streamable_http_path='/' so FastAPI can mount at /mcp.
    Standalone streamable-http keeps default path /mcp on the chosen port.
    """
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "ppt-to-md",
        instructions="Convert PowerPoint .pptx files to Markdown artifact ZIP bundles.",
        streamable_http_path=path,
    )
    settings = ApiSettings()

    @mcp.tool()
    def convert_pptx_to_artifact_zip(pptx_path: str) -> str:
        """Convert a local .pptx path on the server to a temporary artifact.zip path."""
        src = Path(pptx_path).expanduser().resolve()
        if not src.is_file() or src.suffix.lower() != ".pptx":
            raise ValueError("pptx_path must be an existing .pptx file")
        opts = ConvertOptions(artifact_layout=True)
        data = build_artifact_zip_bytes(src, opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="ppt-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def convert_pptx_base64_to_artifact_zip(
        pptx_base64: str,
        filename: str = "upload.pptx",
    ) -> str:
        """Decode a base64-encoded .pptx (optional data:...;base64, prefix) and write artifact.zip path."""
        raw = _decode_base64_pptx(pptx_base64)
        max_b = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_b:
            raise ValueError(f"Decoded file exceeds PPT_TO_MD_MAX_UPLOAD_MB ({settings.max_upload_mb})")
        safe = re.sub(r"[^\w.\-]+", "_", filename) or "upload.pptx"
        if not safe.lower().endswith(".pptx"):
            safe += ".pptx"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / safe
            p.write_bytes(raw)
            opts = ConvertOptions(artifact_layout=True)
            data = build_artifact_zip_bytes(p, opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="ppt-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
