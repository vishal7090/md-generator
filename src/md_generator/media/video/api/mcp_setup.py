from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.media.video.api.settings import VideoApiSettings
from md_generator.media.video.service import VideoToMarkdownService


def _decode_base64(data: str) -> bytes:
    s = data.strip()
    if s.startswith("data:"):
        parts = s.split(",", 1)
        if len(parts) == 2:
            s = parts[1]
    return base64.b64decode(s, validate=False)


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "video-to-md",
        instructions="Extract audio from video, transcribe with Whisper, emit Markdown (paths or base64).",
        streamable_http_path=path,
    )
    settings = VideoApiSettings()

    @mcp.tool()
    def transcribe_video_path(
        video_path: str,
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> str:
        """Transcribe a video file on disk; returns path to a temporary ``.md`` file on the server."""
        src = Path(video_path).expanduser().resolve()
        if not src.is_file():
            raise ValueError("video_path must be an existing file")
        svc = VideoToMarkdownService(whisper_model=whisper_model, language=language)
        fd, name = tempfile.mkstemp(suffix=".md", prefix="video-mcp-")
        os.close(fd)
        out = Path(name)
        try:
            svc.write_markdown(src, out, title=title)
        except Exception:
            out.unlink(missing_ok=True)
            raise
        return str(out)

    @mcp.tool()
    def transcribe_video_base64(
        video_base64: str,
        filename: str = "upload.mp4",
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> str:
        """Decode base64 video (optional ``data:*;base64,`` prefix), transcribe, return path to temporary ``.md``."""
        raw = _decode_base64(video_base64)
        max_b = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_b:
            raise ValueError(f"Decoded file exceeds MD_VIDEO_MAX_UPLOAD_MB ({settings.max_upload_mb})")
        safe = re.sub(r"[^\w.\-]+", "_", filename) or "upload.mp4"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / safe
            p.write_bytes(raw)
            svc = VideoToMarkdownService(whisper_model=whisper_model, language=language)
            fd, name = tempfile.mkstemp(suffix=".md", prefix="video-mcp-b64-")
            os.close(fd)
            out = Path(name)
            try:
                svc.write_markdown(p, out, title=title)
            except Exception:
                out.unlink(missing_ok=True)
                raise
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
