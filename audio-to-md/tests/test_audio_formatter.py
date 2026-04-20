from __future__ import annotations

from md_generator.media.audio.converter import MediaMetadata, TranscriptSegment, TranscriptionResult
from md_generator.media.audio.formatter import AudioMarkdownFormatter, format_timestamped_transcript


def test_format_timestamped_transcript_skips_empty_text() -> None:
    segs = (
        TranscriptSegment(0.0, 1.0, "hello", 0),
        TranscriptSegment(1.0, 2.0, "   ", 1),
        TranscriptSegment(2.0, 3.0, "world", 2),
    )
    out = format_timestamped_transcript(segs)
    assert "hello" in out
    assert "world" in out
    assert "[0:00.000 --> 0:01.000]" in out


def test_audio_markdown_formatter_sections() -> None:
    meta = MediaMetadata(
        title="T",
        duration_seconds=12.345,
        container="wav",
        audio_codec="pcm_s16le",
        sample_rate=16000,
        whisper_language="en",
        whisper_model="base",
        source_path="/tmp/x.wav",
    )
    tr = TranscriptionResult(
        metadata=meta,
        segments=(TranscriptSegment(0.0, 1.0, "Hi", 0),),
        plain_text="Hi",
    )
    md = AudioMarkdownFormatter().format(tr, title_override="Custom")
    assert md.startswith("# Custom\n")
    assert "## Metadata" in md
    assert "## Transcript" in md
    assert "Whisper model" in md
    assert "[0:00.000 --> 0:01.000] Hi" in md


def test_audio_formatter_uses_metadata_title_when_no_override() -> None:
    meta = MediaMetadata(
        title="FromMeta",
        duration_seconds=None,
        container=None,
        audio_codec=None,
        sample_rate=None,
        whisper_language=None,
        whisper_model="tiny",
        source_path="s.wav",
    )
    tr = TranscriptionResult(metadata=meta, segments=(), plain_text="")
    md = AudioMarkdownFormatter().format(tr)
    assert md.startswith("# FromMeta\n")
