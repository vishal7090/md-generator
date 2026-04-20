"""YouTube URL → Markdown (metadata, description, timestamped transcript)."""

from __future__ import annotations

from md_generator.media.youtube.converter import YouTubeConverter
from md_generator.media.youtube.formatter import YouTubeMarkdownFormatter
from md_generator.media.youtube.metadata import (
    YouTubeMetadataError,
    extract_video_id,
    fetch_youtube_metadata,
    normalize_youtube_url,
)
from md_generator.media.youtube.service import (
    YouTubeConversionResult,
    YouTubeError,
    YouTubeToMarkdownService,
    read_youtube_url_from_path,
)
from md_generator.media.youtube.transcript import YouTubeTranscriptError, fetch_transcript

__all__ = [
    "YouTubeConversionResult",
    "YouTubeConverter",
    "YouTubeError",
    "YouTubeMarkdownFormatter",
    "YouTubeMetadataError",
    "YouTubeToMarkdownService",
    "YouTubeTranscriptError",
    "extract_video_id",
    "fetch_transcript",
    "fetch_youtube_metadata",
    "normalize_youtube_url",
    "read_youtube_url_from_path",
]
