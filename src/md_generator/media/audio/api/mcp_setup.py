from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.media.audio.api.settings import AudioApiSettings
from md_generator.media.audio.service import AudioToMarkdownService


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
        "audio-to-md",
        instructions="Transcribe audio files to Markdown using Whisper (local paths or base64 uploads).",
        streamable_http_path=path,
    )
    settings = AudioApiSettings()

    @mcp.tool()
    def transcribe_audio_path(
        audio_path: str,
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> str:
        """Transcribe an audio file on disk; returns path to a temporary ``.md`` file on the server."""
        src = Path(audio_path).expanduser().resolve()
        if not src.is_file():
            raise ValueError("audio_path must be an existing file")
        svc = AudioToMarkdownService(whisper_model=whisper_model, language=language)
        fd, name = tempfile.mkstemp(suffix=".md", prefix="audio-mcp-")
        os.close(fd)
        out = Path(name)
        try:
            svc.write_markdown(src, out, title=title)
        except Exception:
            out.unlink(missing_ok=True)
            raise
        return str(out)

    @mcp.tool()
    def transcribe_audio_base64(
        audio_base64: str,
        filename: str = "upload.mp3",
        whisper_model: str = "base",
        language: str | None = None,
        title: str | None = None,
    ) -> str:
        """Decode base64 audio (optional ``data:*;base64,`` prefix), transcribe, return path to temporary ``.md``."""
        raw = _decode_base64(audio_base64)
        max_b = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_b:
            raise ValueError(f"Decoded file exceeds MD_AUDIO_MAX_UPLOAD_MB ({settings.max_upload_mb})")
        safe = re.sub(r"[^\w.\-]+", "_", filename) or "upload.mp3"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / safe
            p.write_bytes(raw)
            svc = AudioToMarkdownService(whisper_model=whisper_model, language=language)
            fd, name = tempfile.mkstemp(suffix=".md", prefix="audio-mcp-b64-")
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
