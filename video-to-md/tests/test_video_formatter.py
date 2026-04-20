from __future__ import annotations

from pathlib import Path

from md_generator.media.audio.converter import MediaMetadata, TranscriptSegment, TranscriptionResult
from md_generator.media.document_converter import VideoProbeResult
from md_generator.media.video.formatter import VideoMarkdownFormatter


def test_video_markdown_formatter_merges_sections() -> None:
    probe = VideoProbeResult(
        path=Path("in.mp4"),
        duration_seconds=9.0,
        format_name="mov,mp4",
        format_tags_title="Tagged",
        size_bytes=1000,
        video_codec="h264",
        video_width=640,
        video_height=480,
        audio_codec="aac",
        sample_rate=44100,
        raw_ffprobe={},
    )
    meta = MediaMetadata(
        title="ignored-for-video-title",
        duration_seconds=9.0,
        container="wav",
        audio_codec="pcm_s16le",
        sample_rate=16000,
        whisper_language="en",
        whisper_model="base",
        source_path="/tmp/extracted.wav",
    )
    tr = TranscriptionResult(
        metadata=meta,
        segments=(TranscriptSegment(1.0, 2.0, "line", 0),),
        plain_text="line",
    )
    md = VideoMarkdownFormatter().format(
        video_path=Path("clip.mp4"),
        probe=probe,
        transcription=tr,
        title_override="Override",
    )
    assert md.startswith("# Override\n")
    assert "### Video" in md
    assert "### Transcription" in md
    assert "## Transcript" in md
    assert "640×480" in md
    assert "[0:01.000 --> 0:02.000] line" in md
