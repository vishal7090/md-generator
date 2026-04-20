from __future__ import annotations

import pytest

from md_generator.media.youtube.metadata import extract_video_id, normalize_youtube_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("not a url", None),
        ("https://example.com/watch?v=dQw4w9WgXcQ", None),
    ],
)
def test_extract_video_id(url: str, expected: str | None) -> None:
    assert extract_video_id(url) == expected


def test_normalize_youtube_url() -> None:
    assert normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_normalize_invalid_raises() -> None:
    from md_generator.media.youtube.metadata import YouTubeMetadataError

    with pytest.raises(YouTubeMetadataError):
        normalize_youtube_url("https://example.com/")
