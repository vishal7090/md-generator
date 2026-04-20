from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from md_generator.media.audio.converter import MediaMetadata, TranscriptSegment, TranscriptionResult
from md_generator.media.audio.service import AudioToMarkdownService
from md_generator.media.document_converter import VideoProbeResult
from md_generator.media.video.converter import VideoConverter
from md_generator.media.video.formatter import VideoMarkdownFormatter
from md_generator.media.video.service import VideoToMarkdownService


def test_video_service_delegates_transcription_to_audio_service(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"not-a-real-video")

    probe = VideoProbeResult(
        path=video,
        duration_seconds=3.0,
        format_name="mov,mp4",
        format_tags_title=None,
        size_bytes=10,
        video_codec="h264",
        video_width=10,
        video_height=10,
        audio_codec="aac",
        sample_rate=48000,
        raw_ffprobe={},
    )
    tr = TranscriptionResult(
        metadata=MediaMetadata(
            title="x",
            duration_seconds=3.0,
            container="wav",
            audio_codec="pcm_s16le",
            sample_rate=16000,
            whisper_language="en",
            whisper_model="base",
            source_path=str(tmp_path / "extracted_audio.wav"),
        ),
        segments=(TranscriptSegment(0.0, 1.0, "delegated", 0),),
        plain_text="delegated",
    )

    class VC(VideoConverter):
        def convert(self, input_path: Path) -> VideoProbeResult:  # type: ignore[override]
            return probe

        def extract_audio(self, input_video: Path, tmp_dir: Path) -> Path:  # noqa: ARG002
            out = Path(tmp_dir) / "extracted_audio.wav"
            out.write_bytes(b"RIFF")
            return out

    mock_audio = MagicMock(spec=AudioToMarkdownService)
    mock_audio.transcribe.return_value = tr

    svc = VideoToMarkdownService(
        video_converter=VC(),
        audio_service=mock_audio,
        formatter=VideoMarkdownFormatter(),
    )
    md = svc.to_markdown(video)
    assert "delegated" in md
    mock_audio.transcribe.assert_called_once()
    called_path = mock_audio.transcribe.call_args[0][0]
    assert called_path.name == "extracted_audio.wav"
