from __future__ import annotations

from pathlib import Path

import pytest

from md_generator.media.video.service import VideoToMarkdownService


@pytest.fixture()
def _patch_write(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_write_markdown(
        self: VideoToMarkdownService,
        input_video: Path,
        output_md: Path,
        *,
        title: str | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("# video stub\n", encoding=encoding)
        return output_md

    monkeypatch.setattr(VideoToMarkdownService, "write_markdown", fake_write_markdown)


def test_sync_rejects_bad_extension(_patch_write: None) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from md_generator.media.video.api.main import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/convert/sync",
            files={"file": ("x.mp3", b"hi", "audio/mpeg")},
        )
        assert r.status_code == 400


def test_sync_accepts_mp4(_patch_write: None) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from md_generator.media.video.api.main import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/convert/sync",
            files={"file": ("a.mp4", b"fake", "video/mp4")},
        )
        assert r.status_code == 200, r.text
        assert "video stub" in r.text


def test_jobs_flow(_patch_write: None) -> None:
    pytest.importorskip("fastapi")
    import time

    from fastapi.testclient import TestClient

    from md_generator.media.video.api.main import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/convert/jobs",
            files={"file": ("a.mp4", b"fake", "video/mp4")},
        )
        assert r.status_code == 200, r.text
        jid = r.json()["job_id"]
        for _ in range(50):
            st = client.get(f"/convert/jobs/{jid}").json()
            if st["status"] == "done":
                break
            if st["status"] == "failed":
                pytest.fail(st.get("error"))
            time.sleep(0.05)
        dl = client.get(f"/convert/jobs/{jid}/download")
        assert dl.status_code == 200
        assert "video stub" in dl.text
