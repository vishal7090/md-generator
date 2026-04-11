from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_sync_zip_contains_document_and_assets(client: TestClient, minimal_pdf_path: Path) -> None:
    with minimal_pdf_path.open("rb") as f:
        r = client.post(
            "/convert/sync",
            files={"file": ("minimal.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/zip")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "document.md" in names
    assert any(n.startswith("assets/images/") for n in names)


def test_sync_409_when_over_sync_limit(client: TestClient, minimal_pdf_path: Path, monkeypatch) -> None:
    from api import settings

    monkeypatch.setattr(settings, "max_sync_upload_mb", lambda: 0)
    with minimal_pdf_path.open("rb") as f:
        r = client.post(
            "/convert/sync",
            files={"file": ("minimal.pdf", f, "application/pdf")},
        )
    assert r.status_code == 409


def test_sync_413_when_over_upload_limit(client: TestClient, minimal_pdf_path: Path, monkeypatch) -> None:
    from api import settings

    monkeypatch.setattr(settings, "max_upload_mb", lambda: 0)
    with minimal_pdf_path.open("rb") as f:
        r = client.post(
            "/convert/sync",
            files={"file": ("minimal.pdf", f, "application/pdf")},
        )
    assert r.status_code == 413


def test_job_download(client: TestClient, minimal_pdf_path: Path) -> None:
    with minimal_pdf_path.open("rb") as f:
        r = client.post(
            "/convert/jobs",
            files={"file": ("minimal.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    for _ in range(100):
        s = client.get(f"/convert/jobs/{job_id}")
        assert s.status_code == 200
        if s.json()["status"] == "done":
            break
        if s.json()["status"] == "failed":
            pytest.fail(s.json().get("error"))
    else:
        pytest.fail("job did not complete")
    d = client.get(f"/convert/jobs/{job_id}/download")
    assert d.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(d.content))
    assert "document.md" in zf.namelist()
