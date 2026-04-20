"""Extract audio from video with ffmpeg; probe containers with ffprobe (``VideoConverter``)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from md_generator.media.document_converter import (
    DocumentConverter,
    MediaToolsError,
    VideoProbeResult,
    require_ffmpeg_tools,
    resolve_ffmpeg_executable,
    video_probe_from_ffprobe,
)


class VideoConverter(DocumentConverter):
    """ffprobe metadata + ffmpeg audio extraction (no transcription)."""

    _DEFAULT_WAV_NAME = "extracted_audio.wav"
    _FFMPEG_TIMEOUT = 3600

    def convert(self, input_path: Path) -> VideoProbeResult:
        """Return ffprobe-derived metadata only (no transcription)."""
        path = Path(input_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return video_probe_from_ffprobe(path)

    def extract_audio(self, input_video: Path, tmp_dir: Path) -> Path:
        """Extract a mono 16 kHz PCM WAV suitable for Whisper into ``tmp_dir``."""
        require_ffmpeg_tools()
        inp = Path(input_video).resolve()
        if not inp.is_file():
            raise FileNotFoundError(inp)
        out_dir = Path(tmp_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_wav = out_dir / self._DEFAULT_WAV_NAME
        ffmpeg = resolve_ffmpeg_executable()
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(inp),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(out_wav),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._FFMPEG_TIMEOUT,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MediaToolsError("ffmpeg not found on PATH; install FFmpeg.") from exc
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise MediaToolsError(err or f"ffmpeg failed with exit code {proc.returncode}")
        if not out_wav.is_file():
            raise MediaToolsError("ffmpeg did not produce the expected WAV output")
        return out_wav


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Transcribe video to Markdown (extract audio + Whisper).")
    p.add_argument("input", type=Path, help="Input video file path")
    p.add_argument("output", type=Path, help="Output .md file path")
    p.add_argument("--model", default="base", help="Whisper model name (default: base)")
    p.add_argument(
        "--language",
        default=None,
        help=(
            "Whisper language (default: auto-detect if omitted). Single code/name (e.g. en, hi) to force, "
            "or hi,en / hinglish for Hindi+English mixed. Explicit auto / detect matches omitting the flag."
        ),
    )
    p.add_argument("--title", default=None, help="Override document title in Markdown")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        from md_generator.media.video.service import VideoToMarkdownService

        svc = VideoToMarkdownService(whisper_model=args.model, language=args.language)
        out = svc.write_markdown(args.input, args.output, title=args.title)
        if args.verbose:
            print(f"Wrote {out}", file=sys.stderr)
        return 0
    except MediaToolsError as e:
        print(str(e), file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
