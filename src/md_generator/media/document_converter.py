"""Shared document conversion primitives for media-to-Markdown."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class MediaToolsError(RuntimeError):
    """Raised when ffprobe/ffmpeg are missing or return an error."""


def resolve_ffmpeg_executable() -> str:
    """Return an ``ffmpeg`` executable path (PATH, ``FFMPEG`` env, or ``imageio-ffmpeg``)."""
    env = (os.environ.get("FFMPEG") or "").strip()
    if env and Path(env).is_file():
        return env
    w = shutil.which("ffmpeg")
    if w:
        return w
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except Exception:
        pass
    raise MediaToolsError("ffmpeg not found on PATH; install FFmpeg or pip install imageio-ffmpeg.")


def require_ffmpeg_tools() -> None:
    """Ensure ``ffmpeg`` is available (``ffprobe`` is optional; probing falls back to ``ffmpeg -i``)."""
    resolve_ffmpeg_executable()


def _duration_hms_to_seconds(h: str, m: str, s: str) -> float | None:
    try:
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (TypeError, ValueError):
        return None


def _ffprobe_json_via_ffmpeg_stderr(path: Path, *, timeout: int = 120) -> dict[str, Any]:
    """Best-effort ffprobe-like JSON using ``ffmpeg -i`` stderr (when ``ffprobe`` is unavailable)."""
    ffmpeg = resolve_ffmpeg_executable()
    cmd = [ffmpeg, "-hide_banner", "-i", str(path)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaToolsError("ffmpeg not found for metadata probing.") from exc
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    dur_m = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        text,
    )
    duration_seconds: float | None = None
    if dur_m:
        duration_seconds = _duration_hms_to_seconds(dur_m.group(1), dur_m.group(2), dur_m.group(3))

    streams: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "Stream #" not in line or ":" not in line:
            continue
        if " Video:" in line:
            vm = re.search(r"Stream\s+#\d+:\d+(?:\([^)]*\))?:\s*Video:\s*([^,\n]+)", line)
            res_m = re.search(r",\s*(\d+)\s*x\s*(\d+)", line)
            codec = (vm.group(1).strip().split()[0] if vm else None) or None
            w = int(res_m.group(1)) if res_m else None
            h = int(res_m.group(2)) if res_m else None
            if codec:
                streams.append(
                    {
                        "codec_type": "video",
                        "codec_name": codec,
                        "width": w,
                        "height": h,
                    }
                )
        elif " Audio:" in line:
            am = re.search(r"Stream\s+#\d+:\d+(?:\([^)]*\))?:\s*Audio:\s*([^,\n]+)", line)
            hz_m = re.search(r"(\d+)\s+Hz", line)
            raw = am.group(1).strip() if am else ""
            codec = raw.split()[0] if raw else None
            sr = hz_m.group(1) if hz_m else None
            if codec:
                streams.append(
                    {
                        "codec_type": "audio",
                        "codec_name": codec,
                        "sample_rate": sr,
                    }
                )

    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = None
    suffix = path.suffix.lstrip(".") or None
    return {
        "format": {
            "duration": str(duration_seconds) if duration_seconds is not None else None,
            "format_name": suffix,
            "size": str(size_bytes) if size_bytes is not None else None,
            "tags": {},
        },
        "streams": streams,
    }


def ffprobe_json(path: Path, *, timeout: int = 120) -> dict[str, Any]:
    """Run ffprobe and return parsed JSON (format + streams), or fall back to ``ffmpeg -i`` parsing."""
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if shutil.which("ffprobe"):
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MediaToolsError("ffprobe not found on PATH; install FFmpeg.") from exc
        if proc.returncode != 0:
            return _ffprobe_json_via_ffmpeg_stderr(path, timeout=timeout)
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return _ffprobe_json_via_ffmpeg_stderr(path, timeout=timeout)
        if not data.get("format") and not data.get("streams"):
            return _ffprobe_json_via_ffmpeg_stderr(path, timeout=timeout)
        return data

    return _ffprobe_json_via_ffmpeg_stderr(path, timeout=timeout)


@dataclass(frozen=True)
class VideoProbeResult:
    """ffprobe-derived view of a media file (no transcription)."""

    path: Path
    duration_seconds: float | None
    format_name: str | None
    format_tags_title: str | None
    size_bytes: int | None
    video_codec: str | None
    video_width: int | None
    video_height: int | None
    audio_codec: str | None
    sample_rate: int | None
    raw_ffprobe: dict[str, Any] = field(default_factory=dict, repr=False)


def video_probe_from_ffprobe(path: Path, data: dict[str, Any] | None = None) -> VideoProbeResult:
    """Build ``VideoProbeResult`` from ffprobe JSON (fetches ffprobe when ``data`` is None)."""
    if data is None:
        data = ffprobe_json(path)
    fmt = data.get("format") or {}
    tags = fmt.get("tags") or {}
    title = tags.get("title") or tags.get("TITLE")
    duration_raw = fmt.get("duration")
    duration: float | None
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    size_raw = fmt.get("size")
    try:
        size_bytes = int(size_raw) if size_raw is not None else None
    except (TypeError, ValueError):
        size_bytes = None
    format_name = fmt.get("format_name")

    video_codec = video_w = video_h = None
    audio_codec = sample_rate = None
    for stream in data.get("streams") or []:
        ctype = stream.get("codec_type")
        if ctype == "video" and video_codec is None:
            video_codec = stream.get("codec_name")
            try:
                video_w = int(stream["width"]) if stream.get("width") is not None else None
                video_h = int(stream["height"]) if stream.get("height") is not None else None
            except (TypeError, ValueError):
                video_w = video_h = None
        elif ctype == "audio" and audio_codec is None:
            audio_codec = stream.get("codec_name")
            sr = stream.get("sample_rate")
            try:
                sample_rate = int(float(sr)) if sr is not None else None
            except (TypeError, ValueError):
                sample_rate = None

    return VideoProbeResult(
        path=path,
        duration_seconds=duration,
        format_name=format_name,
        format_tags_title=str(title).strip() if title else None,
        size_bytes=size_bytes,
        video_codec=video_codec,
        video_width=video_w,
        video_height=video_h,
        audio_codec=audio_codec,
        sample_rate=sample_rate,
        raw_ffprobe=data,
    )


class DocumentConverter(ABC):
    """Abstract base for converters that turn a file on disk into structured output."""

    @abstractmethod
    def convert(self, input_path: Path) -> Any:
        """Run conversion/analysis for ``input_path``."""
