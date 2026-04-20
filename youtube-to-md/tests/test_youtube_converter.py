from __future__ import annotations

import tempfile
from pathlib import Path

from md_generator.media.youtube.converter import YouTubeConverter


def test_accepts_yturl_and_txt_with_youtube_line() -> None:
    c = YouTubeConverter(enable_audio_fallback=False)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.yturl"
        p.write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ\n", encoding="utf-8")
        assert c.accepts(p) is True

        bad = Path(td) / "plain.txt"
        bad.write_text("hello\n", encoding="utf-8")
        assert c.accepts(bad) is False

        good_txt = Path(td) / "u.txt"
        good_txt.write_text("# comment\nhttps://youtu.be/dQw4w9WgXcQ\n", encoding="utf-8")
        assert c.accepts(good_txt) is True


def test_convert_reads_url(tmp_path: Path) -> None:
    from unittest.mock import patch

    p = tmp_path / "link.url"
    p.write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ", encoding="utf-8")

    fake_meta = {
        "video_id": "dQw4w9WgXcQ",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "T",
        "transcript_source": "youtube_transcript_api",
    }
    fake_seg = [{"start": 0.0, "text": "hi"}]

    with (
        patch("md_generator.media.youtube.service.fetch_youtube_metadata", return_value=fake_meta),
        patch("md_generator.media.youtube.service.fetch_transcript", return_value=fake_seg),
    ):
        c = YouTubeConverter(enable_audio_fallback=False)
        r = c.convert(p)
    assert r.metadata["title"] == "T"
    assert len(r.segments) == 1
    assert r.segments[0]["text"] == "hi"
