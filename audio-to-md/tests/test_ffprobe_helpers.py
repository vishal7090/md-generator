from __future__ import annotations

from pathlib import Path

import pytest

from md_generator.media.document_converter import ffprobe_json, video_probe_from_ffprobe


def test_ffprobe_json_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "dummy.bin"
    p.write_bytes(b"x")
    monkeypatch.setattr(
        "md_generator.media.document_converter.shutil.which",
        lambda name: "ffprobe" if name == "ffprobe" else None,
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        class Proc:
            returncode = 0
            stdout = '{"format":{"duration":"2.5","format_name":"mov,mp4","tags":{"title":"Hello"}},"streams":[{"codec_type":"video","codec_name":"h264","width":1280,"height":720},{"codec_type":"audio","codec_name":"aac","sample_rate":"48000"}]}'
            stderr = ""

        return Proc()

    monkeypatch.setattr("md_generator.media.document_converter.subprocess.run", fake_run)
    data = ffprobe_json(p)
    assert data["format"]["duration"] == "2.5"
    probe = video_probe_from_ffprobe(p, data)
    assert probe.duration_seconds == 2.5
    assert probe.format_tags_title == "Hello"
    assert probe.video_codec == "h264"
    assert probe.video_width == 1280
    assert probe.audio_codec == "aac"
    assert probe.sample_rate == 48000


def test_ffprobe_json_falls_back_to_ffmpeg_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When ffprobe fails, probing uses ``ffmpeg -i`` stderr parsing."""
    p = tmp_path / "dummy.bin"
    p.write_bytes(b"x")
    monkeypatch.setattr(
        "md_generator.media.document_converter.shutil.which",
        lambda name: "ffprobe" if name == "ffprobe" else None,
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        if "-show_streams" in cmd:
            class Bad:
                returncode = 1
                stdout = ""
                stderr = "ffprobe boom"

            return Bad()
        ff_err = (
            "Duration: 00:01:02.50, start: 0.000000, bitrate: 128 kb/s\n"
            "  Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 128 kb/s\n"
        )

        class Ff:
            returncode = 1
            stdout = ""
            stderr = ff_err

        return Ff()

    monkeypatch.setattr("md_generator.media.document_converter.subprocess.run", fake_run)
    data = ffprobe_json(p)
    assert float(data["format"]["duration"]) == pytest.approx(62.5)
    probe = video_probe_from_ffprobe(p, data)
    assert probe.audio_codec == "mp3"
    assert probe.sample_rate == 44100
