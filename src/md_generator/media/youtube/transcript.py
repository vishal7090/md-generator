"""YouTube captions via ``youtube_transcript_api`` with retries and language fallback."""

from __future__ import annotations

import time
from typing import Any


class YouTubeTranscriptError(RuntimeError):
    """Raised when no transcript can be retrieved after retries and fallbacks."""


def _normalize_raw(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw:
        try:
            start = float(item.get("start", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        text = (item.get("text") or "").replace("\n", " ").strip()
        if text:
            out.append({"start": start, "text": text})
    if not out:
        raise YouTubeTranscriptError("Transcript was empty")
    return out


def fetch_transcript(
    video_id: str,
    preferred_languages: list[str] | None = None,
    *,
    attempts: int = 3,
) -> list[dict[str, Any]]:
    """
    Return segments ``[{"start": float, "text": str}, ...]``.

    Tries ``preferred_languages`` in order, then lets the API pick any available transcript.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as e:
        raise YouTubeTranscriptError(
            "youtube-transcript-api is not installed; pip install mdengine[youtube]"
        ) from e

    langs = [x.strip().lower() for x in (preferred_languages or []) if x and x.strip()]

    def fetch_raw_legacy() -> list[dict[str, Any]]:
        if langs:
            try:
                return YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            except NoTranscriptFound:
                return YouTubeTranscriptApi.get_transcript(video_id)
        return YouTubeTranscriptApi.get_transcript(video_id)

    def fetch_raw_modern() -> list[dict[str, Any]]:
        api = YouTubeTranscriptApi()
        if langs:
            try:
                return list(api.fetch(video_id, languages=tuple(langs)).to_raw_data())
            except NoTranscriptFound:
                pass
        try:
            return list(api.fetch(video_id).to_raw_data())
        except NoTranscriptFound:
            tlist = api.list(video_id)
            for tr in tlist:
                try:
                    return list(tr.fetch().to_raw_data())
                except Exception:
                    continue
            raise YouTubeTranscriptError(f"No transcripts available for video {video_id}")

    def try_fetch() -> list[dict[str, Any]]:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            raw = fetch_raw_legacy()
        else:
            raw = fetch_raw_modern()
        return _normalize_raw(raw)

    last: Exception | None = None
    for i in range(attempts):
        try:
            return try_fetch()
        except (TranscriptsDisabled, VideoUnavailable) as e:
            raise YouTubeTranscriptError(str(e)) from e
        except NoTranscriptFound as e:
            raise YouTubeTranscriptError(str(e)) from e
        except YouTubeTranscriptError:
            raise
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(0.5 * (2**i))
    raise YouTubeTranscriptError(str(last) if last else "Transcript fetch failed")
