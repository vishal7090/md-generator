"""Video → Markdown: ffmpeg extract + delegate transcription to ``AudioToMarkdownService``."""

from __future__ import annotations

import tempfile
from pathlib import Path

from md_generator.media.audio.converter import TranscriptionResult
from md_generator.media.audio.service import AudioToMarkdownService
from md_generator.media.document_converter import VideoProbeResult
from md_generator.media.video.converter import VideoConverter
from md_generator.media.video.formatter import VideoMarkdownFormatter


class VideoToMarkdownService:
    """Extract audio from video, transcribe via audio service only, then format."""

    def __init__(
        self,
        *,
        video_converter: VideoConverter | None = None,
        audio_service: AudioToMarkdownService | None = None,
        formatter: VideoMarkdownFormatter | None = None,
        whisper_model: str = "base",
        language: str | None = None,
    ) -> None:
        self._video = video_converter or VideoConverter()
        self._audio = audio_service or AudioToMarkdownService(whisper_model=whisper_model, language=language)
        self._formatter = formatter or VideoMarkdownFormatter()

    @property
    def video_converter(self) -> VideoConverter:
        return self._video

    @property
    def audio_service(self) -> AudioToMarkdownService:
        return self._audio

    @property
    def formatter(self) -> VideoMarkdownFormatter:
        return self._formatter

    def probe(self, input_video: Path) -> VideoProbeResult:
        return self._video.convert(Path(input_video))

    def transcribe_via_extracted_audio(
        self,
        input_video: Path,
    ) -> tuple[VideoProbeResult, TranscriptionResult]:
        """Extract audio to a temp WAV and return ``(probe, transcription)``."""
        video_path = Path(input_video).resolve()
        probe = self.probe(video_path)
        with tempfile.TemporaryDirectory() as td:
            wav_path = self._video.extract_audio(video_path, Path(td))
            transcription = self._audio.transcribe(wav_path)
        return probe, transcription

    def to_markdown(self, input_video: Path, *, title: str | None = None) -> str:
        probe, transcription = self.transcribe_via_extracted_audio(Path(input_video))
        return self._formatter.format(
            video_path=Path(input_video),
            probe=probe,
            transcription=transcription,
            title_override=title,
        )

    def write_markdown(
        self,
        input_video: Path,
        output_md: Path,
        *,
        title: str | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        body = self.to_markdown(input_video, title=title)
        output_md.write_text(body, encoding=encoding)
        return output_md
