from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    def _fake_convert(staged: Path, output_md: Path, opts) -> None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("# fake\n", encoding="utf-8")

    monkeypatch.setattr("md_generator.image.api.main.convert_images_recursive", _fake_convert)
    from fastapi.testclient import TestClient

    from md_generator.image.api.main import app

    return TestClient(app)


def test_convert_sync_returns_zip(api_client) -> None:
    r = api_client.post(
        "/convert/sync",
        files={"file": ("a.png", _png_bytes(), "image/png")},
        params={"engines": "easy", "strategy": "best"},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(r.content), "r") as zf:
        names = zf.namelist()
    assert any(n.endswith("document.md") for n in names)


def test_convert_job_lifecycle(api_client) -> None:
    r = api_client.post(
        "/convert/jobs",
        files={"file": ("b.png", _png_bytes(), "image/png")},
        params={"engines": "easy"},
    )
    assert r.status_code == 200
    jid = r.json()["job_id"]
    st = api_client.get(f"/convert/jobs/{jid}")
    assert st.json()["status"] in ("queued", "running", "done")
    import time

    for _ in range(50):
        st = api_client.get(f"/convert/jobs/{jid}")
        if st.json()["status"] == "done":
            break
        time.sleep(0.05)
    assert st.json()["status"] == "done"
    dl = api_client.get(f"/convert/jobs/{jid}/download")
    assert dl.status_code == 200
    assert dl.content[:2] == b"PK"


def test_convert_sync_rejects_bad_extension(api_client) -> None:
    r = api_client.post(
        "/convert/sync",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
