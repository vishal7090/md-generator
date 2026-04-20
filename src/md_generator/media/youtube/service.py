"""Orchestrate metadata + transcript (+ optional Whisper fallback) for YouTube URLs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from md_generator.media.youtube.formatter import YouTubeMarkdownFormatter
from md_generator.media.youtube.metadata import (
    YouTubeMetadataError,
    extract_video_id,
    fetch_youtube_metadata,
    normalize_youtube_url,
)
from md_generator.media.youtube.transcript import YouTubeTranscriptError, fetch_transcript


class YouTubeError(RuntimeError):
    """Base error for YouTube conversion."""


@dataclass
class YouTubeConversionResult:
    """Structured output from ``YouTubeToMarkdownService.build_result``."""

    metadata: dict[str, Any]
    segments: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class YouTubeToMarkdownService:
    """Fetch metadata and transcript, optionally fall back to Whisper on downloaded audio."""

    def __init__(
        self,
        *,
        formatter: YouTubeMarkdownFormatter | None = None,
        whisper_model: str = "base",
        whisper_language: str | None = None,
    ) -> None:
        self._formatter = formatter or YouTubeMarkdownFormatter()
        self._whisper_model = whisper_model
        self._whisper_language = whisper_language

    def build_result(
        self,
        url: str,
        *,
        transcript_languages: list[str] | None = None,
        enable_audio_fallback: bool = True,
    ) -> YouTubeConversionResult:
        vid = extract_video_id(url)
        if not vid:
            raise YouTubeError(f"Invalid or unsupported YouTube URL: {url!r}")
        watch = normalize_youtube_url(url)

        meta = fetch_youtube_metadata(vid, watch)
        meta = {**meta, "transcript_source": "youtube_transcript_api"}

        try:
            segments = fetch_transcript(vid, transcript_languages)
        except YouTubeTranscriptError:
            if not enable_audio_fallback:
                raise
            segments, meta = self._transcribe_via_ytdlp(watch, meta)
        seg_tup = tuple(dict(s) for s in segments)
        return YouTubeConversionResult(metadata=meta, segments=seg_tup)

    def _resolve_ytdlp(self) -> str:
        env = (os.environ.get("MD_YOUTUBE_YTDLP") or "").strip()
        if env and Path(env).is_file():
            return env
        w = shutil.which("yt-dlp")
        if w:
            return w
        raise YouTubeError(
            "Transcript unavailable and audio fallback is enabled, but yt-dlp was not found. "
            "Install yt-dlp on PATH or set MD_YOUTUBE_YTDLP to the executable, "
            "or pass enable_audio_fallback=False."
        )

    def _transcribe_via_ytdlp(self, watch_url: str, meta: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ytdlp = self._resolve_ytdlp()
        try:
            from md_generator.media.audio.service import AudioToMarkdownService
        except ImportError as e:
            raise YouTubeError(
                "Audio fallback requires mdengine[audio] (Whisper). pip install mdengine[audio]"
            ) from e

        whisper_dur: float | None = None
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_tmpl = str(td_path / "audio.%(ext)s")
            cmd = [
                ytdlp,
                "--no-playlist",
                "-f",
                "bestaudio/best",
                "-x",
                "--audio-format",
                "m4a",
                "-o",
                out_tmpl,
                "--",
                watch_url,
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                    check=False,
                )
            except FileNotFoundError as e:
                raise YouTubeError(f"yt-dlp failed to execute: {ytdlp}") from e
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()
                raise YouTubeError(err or f"yt-dlp exited with code {proc.returncode}")

            audio_files = sorted(td_path.glob("audio.*"))
            if not audio_files:
                raise YouTubeError("yt-dlp did not produce an audio file in the temp directory")
            audio_path = audio_files[0]

            svc = AudioToMarkdownService(whisper_model=self._whisper_model, language=self._whisper_language)
            tr = svc.transcribe(audio_path)
            segments = [{"start": s.start, "text": s.text} for s in tr.segments if s.text.strip()]
            whisper_dur = tr.metadata.duration_seconds

        meta = {**meta, "transcript_source": "whisper (yt-dlp audio)"}
        if meta.get("duration_seconds") is None and whisper_dur is not None:
            meta["duration_seconds"] = whisper_dur
        return segments, meta

    def to_markdown(
        self,
        url: str,
        *,
        title_override: str | None = None,
        transcript_languages: list[str] | None = None,
        enable_audio_fallback: bool = True,
    ) -> str:
        result = self.build_result(
            url,
            transcript_languages=transcript_languages,
            enable_audio_fallback=enable_audio_fallback,
        )
        meta = dict(result.metadata)
        if title_override:
            meta["title"] = title_override.strip()
        patched = YouTubeConversionResult(metadata=meta, segments=result.segments)
        return self._formatter.format(patched)

    def write_markdown(
        self,
        url: str,
        output_md: Path,
        *,
        title: str | None = None,
        transcript_languages: list[str] | None = None,
        enable_audio_fallback: bool = True,
        encoding: str = "utf-8",
    ) -> Path:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        body = self.to_markdown(
            url,
            title_override=title,
            transcript_languages=transcript_languages,
            enable_audio_fallback=enable_audio_fallback,
        )
        output_md.write_text(body, encoding=encoding)
        return output_md


def read_youtube_url_from_path(path: Path) -> str:
    """Read first non-empty, non-comment line from a text file as the YouTube URL."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return s
    raise YouTubeError(f"No YouTube URL found in file: {path}")


__all__ = [
    "YouTubeConversionResult",
    "YouTubeError",
    "YouTubeMetadataError",
    "YouTubeToMarkdownService",
    "YouTubeTranscriptError",
    "read_youtube_url_from_path",
]
