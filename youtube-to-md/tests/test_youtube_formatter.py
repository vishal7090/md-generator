from __future__ import annotations

from md_generator.media.youtube.formatter import YouTubeMarkdownFormatter
from md_generator.media.youtube.service import YouTubeConversionResult


def test_youtube_markdown_formatter() -> None:
    result = YouTubeConversionResult(
        metadata={
            "title": "Sample",
            "url": "https://www.youtube.com/watch?v=abc",
            "views": 1000,
            "duration_seconds": 42.5,
            "keywords": "a, b",
            "author": "Channel",
            "transcript_source": "youtube_transcript_api",
            "description": "Hello **world**",
        },
        segments=({"start": 0.0, "text": "Line one"}, {"start": 5.2, "text": "Line two"}),
    )
    md = YouTubeMarkdownFormatter().format(result)
    assert md.startswith("# YouTube\n\n## Sample\n")
    assert "### Video Metadata" in md
    assert "**Views:** 1000" in md
    assert "### Description" in md
    assert "Hello **world**" in md
    assert "### Transcript" in md
    assert "[0.00s] Line one" in md
    assert "[5.20s] Line two" in md
