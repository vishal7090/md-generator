from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.media.youtube.service import YouTubeToMarkdownService


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "youtube-to-md",
        instructions="Convert a public YouTube URL to Markdown (metadata + transcript; optional Whisper fallback).",
        streamable_http_path=path,
    )
    @mcp.tool()
    def youtube_url_to_markdown(
        url: str,
        title: str | None = None,
        transcript_languages: str | None = None,
        enable_audio_fallback: bool = True,
        whisper_model: str = "base",
        language: str | None = None,
    ) -> str:
        """Write Markdown to a temporary ``.md`` file; returns its path on the server."""
        langs = [x.strip() for x in (transcript_languages or "").split(",") if x.strip()] or None
        svc = YouTubeToMarkdownService(whisper_model=whisper_model, whisper_language=language)
        fd, name = tempfile.mkstemp(suffix=".md", prefix="youtube-mcp-")
        os.close(fd)
        out = Path(name)
        try:
            svc.write_markdown(
                url.strip(),
                out,
                title=title,
                transcript_languages=langs,
                enable_audio_fallback=enable_audio_fallback,
            )
        except Exception:
            out.unlink(missing_ok=True)
            raise
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
