"""Markdown for video: container/stream metadata plus reused timestamped transcript."""

from __future__ import annotations

from pathlib import Path

from md_generator.media.audio.converter import TranscriptionResult
from md_generator.media.audio.formatter import format_timestamped_transcript
from md_generator.media.document_converter import VideoProbeResult


def _video_metadata_lines(video_path: Path, probe: VideoProbeResult) -> list[str]:
    lines = [
        f"- **Video file:** `{video_path.resolve()}`",
    ]
    if probe.duration_seconds is not None:
        lines.append(f"- **Duration (seconds):** {probe.duration_seconds:.3f}")
    if probe.format_name:
        lines.append(f"- **Container / format:** {probe.format_name}")
    if probe.size_bytes is not None:
        lines.append(f"- **Size (bytes):** {probe.size_bytes}")
    if probe.video_codec:
        lines.append(f"- **Video codec:** {probe.video_codec}")
    if probe.video_width and probe.video_height:
        lines.append(f"- **Resolution:** {probe.video_width}×{probe.video_height}")
    if probe.audio_codec:
        lines.append(f"- **Muxed audio codec:** {probe.audio_codec}")
    if probe.sample_rate is not None:
        lines.append(f"- **Muxed audio sample rate (Hz):** {probe.sample_rate}")
    return lines


def _transcription_metadata_lines(tr: TranscriptionResult) -> list[str]:
    meta = tr.metadata
    lines = [
        "- **Pipeline:** audio extracted to mono 16 kHz WAV, then transcribed with Whisper",
        f"- **Whisper model:** {meta.whisper_model}",
    ]
    if meta.whisper_language:
        lines.append(f"- **Detected / set language:** {meta.whisper_language}")
    return lines


class VideoMarkdownFormatter:
    """Compose video probe metadata with transcript from ``TranscriptionResult``."""

    def format(
        self,
        *,
        video_path: Path,
        probe: VideoProbeResult,
        transcription: TranscriptionResult,
        title_override: str | None = None,
    ) -> str:
        title = (
            title_override
            or probe.format_tags_title
            or Path(video_path).stem
            or transcription.metadata.title
            or "Untitled"
        ).strip()

        parts = [
            f"# {title}",
            "",
            "## Metadata",
            "",
            "### Video",
            "",
            *_video_metadata_lines(Path(video_path), probe),
            "",
            "### Transcription",
            "",
            *_transcription_metadata_lines(transcription),
            "",
            "## Transcript",
            "",
            format_timestamped_transcript(transcription.segments),
            "",
        ]
        return "\n".join(parts).rstrip() + "\n"
