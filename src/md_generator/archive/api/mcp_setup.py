from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.archive.api.convert_runner import build_artifact_zip_bytes
from md_generator.archive.api.query_options import convert_options_from_query
from md_generator.archive.api.settings import ApiSettings
from md_generator.archive.extractors import archive_filename_suffix, detect_archive_format, is_supported_archive_filename
from md_generator.archive.options import ConvertOptions


def _decode_base64_zip(data: str) -> bytes:
    s = data.strip()
    if s.startswith("data:"):
        parts = s.split(",", 1)
        if len(parts) == 2:
            s = parts[1]
    return base64.b64decode(s, validate=False)


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "zip-to-md",
        instructions="Convert archives (.zip, .tar, .tar.gz, .tgz, .tar.bz2, .7z, .rar) to Markdown artifact ZIP bundles.",
        streamable_http_path=path,
    )
    settings = ApiSettings()

    def _opts() -> ConvertOptions:
        return convert_options_from_query(
            repo_root=settings.repo_root,
            use_image_to_md=settings.use_image_to_md,
            image_to_md_engines=settings.image_to_md_engines,
            image_to_md_strategy=settings.image_to_md_strategy,
            image_to_md_title=settings.image_to_md_title,
        )

    @mcp.tool()
    def convert_zip_to_artifact_zip(zip_path: str) -> str:
        """Convert a local archive path on the server to a temporary artifact.zip path."""
        src = Path(zip_path).expanduser().resolve()
        if not src.is_file() or detect_archive_format(src) is None:
            raise ValueError("zip_path must be an existing supported archive file")
        data = build_artifact_zip_bytes(src, _opts())
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="zip-to-md-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def convert_zip_base64_to_artifact_zip(
        zip_base64: str,
        filename: str = "upload.zip",
    ) -> str:
        """Decode base64 archive (optional data:...;base64, prefix) and write artifact.zip path."""
        raw = _decode_base64_zip(zip_base64)
        max_b = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_b:
            raise ValueError(f"Decoded file exceeds ZIP_TO_MD_MAX_UPLOAD_MB ({settings.max_upload_mb})")
        safe = re.sub(r"[^\w.\-]+", "_", filename) or "upload.zip"
        if not is_supported_archive_filename(safe):
            safe = f"{safe}.zip" if not safe.lower().endswith(".zip") else safe
        if not is_supported_archive_filename(safe):
            safe = "upload.zip"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / safe
            p.write_bytes(raw)
            data = build_artifact_zip_bytes(p, _opts())
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="zip-to-md-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
