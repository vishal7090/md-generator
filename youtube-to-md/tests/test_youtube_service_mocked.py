from __future__ import annotations

from unittest.mock import patch

from md_generator.media.youtube.service import YouTubeToMarkdownService


def test_to_markdown_mocked() -> None:
    fake_meta = {
        "video_id": "dQw4w9WgXcQ",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Mocked",
        "transcript_source": "youtube_transcript_api",
    }
    fake_seg = [{"start": 1.0, "text": "only"}]

    with (
        patch("md_generator.media.youtube.service.fetch_youtube_metadata", return_value=fake_meta),
        patch("md_generator.media.youtube.service.fetch_transcript", return_value=fake_seg),
    ):
        svc = YouTubeToMarkdownService()
        md = svc.to_markdown(
            "https://youtu.be/dQw4w9WgXcQ",
            enable_audio_fallback=False,
        )
    assert "Mocked" in md
    assert "[1.00s] only" in md
