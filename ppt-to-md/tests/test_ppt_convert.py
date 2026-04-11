from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from md_generator.ppt.convert_impl import convert_pptx
from md_generator.ppt.options import ConvertOptions

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal.pptx"


@pytest.fixture(scope="module")
def fixture_pptx() -> Path:
    assert FIXTURE.is_file(), "Run python tests/build_fixture.py first"
    return FIXTURE


def test_classic_conversion(fixture_pptx: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    convert_pptx(
        fixture_pptx,
        out,
        ConvertOptions(artifact_layout=False, title_slide_h1=True),
    )
    text = out.read_text(encoding="utf-8")
    assert "# Fixture Title" in text
    assert "Bullet one" in text
    assert "| H1 |" in text
    assert "Speaker note line" in text
    assert (out.parent / "images" / "slide_2_img_1.png").is_file()


def test_artifact_layout(fixture_pptx: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "artifact"
    convert_pptx(
        fixture_pptx,
        out_dir,
        ConvertOptions(artifact_layout=True, extract_embedded_deep=False),
    )
    doc = out_dir / "document.md"
    assert doc.is_file()
    body = doc.read_text(encoding="utf-8")
    assert "## Slide 1: Fixture Title" in body
    assert "assets/images/slide_2_img_1.png" in body or "slide_2_img_1.png" in body
    assert (out_dir / "assets" / "extraction_manifest.json").is_file()
    assert (out_dir / "assets" / "media").is_dir()


def test_artifact_zip_roundtrip(fixture_pptx: Path, tmp_path: Path) -> None:
    from md_generator.ppt.api.convert_runner import build_artifact_zip_bytes

    zbytes = build_artifact_zip_bytes(
        fixture_pptx,
        ConvertOptions(artifact_layout=True, extract_embedded_deep=False),
    )
    zpath = tmp_path / "a.zip"
    zpath.write_bytes(zbytes)
    with zipfile.ZipFile(zpath, "r") as zf:
        names = zf.namelist()
    assert "document.md" in names
    assert any(n.startswith("assets/") for n in names)


def test_api_sync_and_jobs(fixture_pptx: Path, tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from md_generator.ppt.api.main import app

    with TestClient(app) as client:
        fixture_pptx.read_bytes()
        r = client.post(
            "/convert/sync",
            files={"file": ("minimal.pptx", fixture_pptx.read_bytes(), "application/vnd.ms-powerpoint")},
            params={"extract_embedded_deep": "false"},
        )
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")

        r2 = client.post(
            "/convert/jobs",
            files={"file": ("minimal.pptx", fixture_pptx.read_bytes(), "application/vnd.ms-powerpoint")},
            params={"extract_embedded_deep": "false"},
        )
        assert r2.status_code == 200, r2.text
        jid = r2.json()["job_id"]
        import time

        for _ in range(50):
            st = client.get(f"/convert/jobs/{jid}").json()
            if st["status"] == "done":
                break
            if st["status"] == "failed":
                pytest.fail(st.get("error"))
            time.sleep(0.05)
        dl = client.get(f"/convert/jobs/{jid}/download")
        assert dl.status_code == 200
        assert dl.headers.get("content-type", "").startswith("application/zip")
