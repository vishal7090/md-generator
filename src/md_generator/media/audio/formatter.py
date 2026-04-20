"""Render ``TranscriptionResult`` as Markdown (title, metadata, timestamped transcript)."""

from __future__ import annotations

from md_generator.media.audio.converter import MediaMetadata, TranscriptSegment, TranscriptionResult


def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds % 1.0) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:d}:{s:02d}.{ms:03d}"


def format_timestamped_transcript(segments: tuple[TranscriptSegment, ...]) -> str:
    """Format segments as timestamped lines (shared with video module)."""
    lines: list[str] = []
    for seg in segments:
        a = _format_timestamp(seg.start)
        b = _format_timestamp(seg.end)
        t = seg.text.strip()
        if not t:
            continue
        lines.append(f"[{a} --> {b}] {t}")
    return "\n".join(lines) if lines else "_(no speech detected)_"


def _metadata_lines(meta: MediaMetadata) -> list[str]:
    lines = [
        f"- **Source:** `{meta.source_path}`",
        f"- **Whisper model:** {meta.whisper_model}",
    ]
    if meta.duration_seconds is not None:
        lines.append(f"- **Duration (seconds):** {meta.duration_seconds:.3f}")
    if meta.container:
        lines.append(f"- **Container / format:** {meta.container}")
    if meta.audio_codec:
        lines.append(f"- **Audio codec:** {meta.audio_codec}")
    if meta.sample_rate is not None:
        lines.append(f"- **Sample rate (Hz):** {meta.sample_rate}")
    if meta.language_profile:
        lines.append(f"- **Language option:** {meta.language_profile}")
    if meta.whisper_language:
        lines.append(f"- **Detected language (Whisper):** {meta.whisper_language}")
    return lines


class AudioMarkdownFormatter:
    """Build Markdown with title, metadata, and timestamped transcript."""

    def format(self, result: TranscriptionResult, *, title_override: str | None = None) -> str:
        title = (title_override or result.metadata.title or "Untitled").strip()
        parts = [
            f"# {title}",
            "",
            "## Metadata",
            "",
            *_metadata_lines(result.metadata),
            "",
            "## Transcript",
            "",
            format_timestamped_transcript(result.segments),
            "",
        ]
        return "\n".join(parts).rstrip() + "\n"
