"""Whisper transcription + ffprobe metadata (``AudioConverter``)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from md_generator.media.document_converter import (
    DocumentConverter,
    MediaToolsError,
    ffprobe_json,
    video_probe_from_ffprobe,
)
from md_generator.media.whisper_language import resolve_whisper_language


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    id: int | None = None


@dataclass
class MediaMetadata:
    title: str
    duration_seconds: float | None
    container: str | None
    audio_codec: str | None
    sample_rate: int | None
    whisper_language: str | None
    whisper_model: str
    source_path: str
    language_profile: str | None = None


@dataclass
class TranscriptionResult:
    metadata: MediaMetadata
    segments: tuple[TranscriptSegment, ...]
    plain_text: str


def _metadata_from_ffprobe(path: Path, whisper_model: str, whisper_language: str | None) -> MediaMetadata:
    data = ffprobe_json(path)
    probe = video_probe_from_ffprobe(path, data)
    title = probe.format_tags_title or path.stem or "Untitled"
    return MediaMetadata(
        title=title,
        duration_seconds=probe.duration_seconds,
        container=probe.format_name,
        audio_codec=probe.audio_codec,
        sample_rate=probe.sample_rate,
        whisper_language=whisper_language,
        whisper_model=whisper_model,
        source_path=str(path.resolve()),
    )


class AudioConverter(DocumentConverter):
    """Transcribe audio with Whisper and attach ffprobe metadata."""

    def __init__(
        self,
        *,
        model_name: str = "base",
        language: str | None = None,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._device = device
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_model(self) -> Any:
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self._model_name, device=self._device)
        return self._model

    def convert(self, input_path: Path) -> TranscriptionResult:
        path = Path(input_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)

        meta = _metadata_from_ffprobe(path, self._model_name, None)
        model = self._load_model()
        lang_kw, init_prompt, profile = resolve_whisper_language(self._language)
        kwargs: dict = {"verbose": False}
        if lang_kw:
            kwargs["language"] = lang_kw
        if init_prompt:
            kwargs["initial_prompt"] = init_prompt
        asr = model.transcribe(str(path), **kwargs)
        whisper_lang = asr.get("language")
        text = (asr.get("text") or "").strip()
        raw_segments = asr.get("segments") or []
        segments: list[TranscriptSegment] = []
        for i, seg in enumerate(raw_segments):
            try:
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", 0.0))
            except (TypeError, ValueError):
                start, end = 0.0, 0.0
            t = (seg.get("text") or "").strip()
            seg_id = seg.get("id")
            try:
                sid = int(seg_id) if seg_id is not None else i
            except (TypeError, ValueError):
                sid = i
            segments.append(TranscriptSegment(start=start, end=end, text=t, id=sid))

        meta = MediaMetadata(
            title=meta.title,
            duration_seconds=meta.duration_seconds,
            container=meta.container,
            audio_codec=meta.audio_codec,
            sample_rate=meta.sample_rate,
            whisper_language=whisper_lang,
            whisper_model=self._model_name,
            source_path=meta.source_path,
            language_profile=profile,
        )
        return TranscriptionResult(
            metadata=meta,
            segments=tuple(segments),
            plain_text=text,
        )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Transcribe audio to Markdown via Whisper.")
    p.add_argument("input", type=Path, help="Input audio file path")
    p.add_argument("output", type=Path, help="Output .md file path")
    p.add_argument("--model", default="base", help="Whisper model name (default: base)")
    p.add_argument(
        "--language",
        default=None,
        help=(
            "Whisper language (default: auto-detect if omitted). Single code/name (e.g. en, hi) to force, "
            "or hi,en / hinglish for Hindi+English mixed (auto-detect + bilingual prompt). "
            "Explicit auto / detect is the same as omitting this flag."
        ),
    )
    p.add_argument("--title", default=None, help="Override document title in Markdown")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        from md_generator.media.audio.service import AudioToMarkdownService

        svc = AudioToMarkdownService(whisper_model=args.model, language=args.language)
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


if __name__ == "__main__":
    raise SystemExit(main())
