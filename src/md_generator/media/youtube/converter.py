"""CLI and ``DocumentConverter`` entry for YouTube URL files → structured result / Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.media.document_converter import DocumentConverter
from md_generator.media.youtube.service import (
    YouTubeConversionResult,
    YouTubeError,
    YouTubeToMarkdownService,
    read_youtube_url_from_path,
)
from md_generator.media.youtube.metadata import extract_video_id


class YouTubeConverter(DocumentConverter):
    """
    ``convert(path)`` reads a small text file containing one YouTube URL per line
    (first non-empty line wins). Use ``accepts(path)`` to detect supported files.
    """

    def __init__(
        self,
        *,
        service: YouTubeToMarkdownService | None = None,
        transcript_languages: list[str] | None = None,
        enable_audio_fallback: bool = True,
    ) -> None:
        self._service = service or YouTubeToMarkdownService()
        self._transcript_languages = transcript_languages
        self._enable_audio_fallback = enable_audio_fallback

    def accepts(self, input_path: Path) -> bool:
        p = Path(input_path)
        if not p.is_file():
            return False
        suf = p.suffix.lower()
        if suf in (".url", ".yturl", ".youtube"):
            return True
        if suf == ".txt":
            try:
                url = read_youtube_url_from_path(p)
            except YouTubeError:
                return False
            return extract_video_id(url) is not None
        return False

    def convert(self, input_path: Path) -> YouTubeConversionResult:
        path = Path(input_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        url = read_youtube_url_from_path(path)
        return self._service.build_result(
            url,
            transcript_languages=self._transcript_languages,
            enable_audio_fallback=self._enable_audio_fallback,
        )


def _parse_lang_list(s: str | None) -> list[str] | None:
    if not s or not str(s).strip():
        return None
    parts = [p.strip() for p in str(s).split(",") if p.strip()]
    return parts or None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert a YouTube URL to Markdown (metadata + transcript).")
    p.add_argument("url", help="YouTube watch / youtu.be / shorts URL")
    p.add_argument("output", type=Path, help="Output .md file path")
    p.add_argument("--title", default=None, help="Override title in Markdown")
    p.add_argument(
        "--transcript-lang",
        dest="transcript_langs",
        action="append",
        default=None,
        metavar="CODE",
        help="Preferred transcript language (repeatable), e.g. --transcript-lang hi --transcript-lang en",
    )
    p.add_argument(
        "--transcript-langs",
        dest="transcript_langs_csv",
        default=None,
        metavar="CODES",
        help="Comma-separated preferred transcript languages (alternative to --transcript-lang)",
    )
    p.add_argument(
        "--no-audio-fallback",
        action="store_true",
        help="Do not download audio with yt-dlp + Whisper if captions are missing",
    )
    p.add_argument("--whisper-model", default="base", help="Whisper model when audio fallback runs (default: base)")
    p.add_argument(
        "--language",
        default=None,
        help="Whisper language when audio fallback runs (same semantics as md-audio)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    langs: list[str] | None = None
    if args.transcript_langs:
        langs = []
        for item in args.transcript_langs:
            langs.extend([x.strip() for x in item.split(",") if x.strip()])
        langs = langs or None
    elif args.transcript_langs_csv:
        langs = _parse_lang_list(args.transcript_langs_csv)

    try:
        svc = YouTubeToMarkdownService(
            whisper_model=args.whisper_model,
            whisper_language=args.language,
        )
        out = svc.write_markdown(
            args.url.strip(),
            args.output,
            title=args.title,
            transcript_languages=langs,
            enable_audio_fallback=not args.no_audio_fallback,
        )
        if args.verbose:
            print(f"Wrote {out}", file=sys.stderr)
        return 0
    except YouTubeError as e:
        print(str(e), file=sys.stderr)
        return 2
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())