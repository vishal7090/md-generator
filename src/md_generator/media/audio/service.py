"""Audio → Markdown orchestration service."""

from __future__ import annotations

from pathlib import Path

from md_generator.media.audio.converter import AudioConverter, TranscriptionResult
from md_generator.media.audio.formatter import AudioMarkdownFormatter


class AudioToMarkdownService:
    """Transcribe audio and render Markdown using ``AudioConverter`` + ``AudioMarkdownFormatter``."""

    def __init__(
        self,
        *,
        converter: AudioConverter | None = None,
        formatter: AudioMarkdownFormatter | None = None,
        whisper_model: str = "base",
        language: str | None = None,
    ) -> None:
        self._converter = converter or AudioConverter(model_name=whisper_model, language=language)
        self._formatter = formatter or AudioMarkdownFormatter()

    @property
    def converter(self) -> AudioConverter:
        return self._converter

    @property
    def formatter(self) -> AudioMarkdownFormatter:
        return self._formatter

    def transcribe(self, input_audio: Path) -> TranscriptionResult:
        return self._converter.convert(Path(input_audio))

    def to_markdown(self, input_audio: Path, *, title: str | None = None) -> str:
        result = self.transcribe(Path(input_audio))
        return self._formatter.format(result, title_override=title)

    def write_markdown(
        self,
        input_audio: Path,
        output_md: Path,
        *,
        title: str | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        body = self.to_markdown(input_audio, title=title)
        output_md.write_text(body, encoding=encoding)
        return output_md
