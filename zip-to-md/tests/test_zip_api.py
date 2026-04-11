from __future__ import annotations

import io
import zipfile

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from md_generator.archive.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Module scope: MCP session manager allows a single lifespan run per process."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tiny_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "api test\n")
    return buf.getvalue()


def test_sync_returns_artifact_zip(client: TestClient, tiny_zip_bytes: bytes) -> None:
    r = client.post(
        "/convert/sync",
        files={"file": ("sample.zip", tiny_zip_bytes, "application/zip")},
        params={"enable_office": "false"},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/zip")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "document.md" in names
    assert any(n.startswith("assets/files/") for n in names)
    doc = zf.read("document.md").decode("utf-8")
    assert "api test" in doc


def test_job_download_roundtrip(client: TestClient, tiny_zip_bytes: bytes) -> None:
    r = client.post(
        "/convert/jobs",
        files={"file": ("job.zip", tiny_zip_bytes, "application/zip")},
        params={"enable_office": "false"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    for _ in range(100):
        s = client.get(f"/convert/jobs/{job_id}")
        assert s.status_code == 200
        st = s.json()["status"]
        if st == "done":
            break
        if st == "failed":
            pytest.fail(s.json().get("error"))
    else:
        pytest.fail("job did not complete")
    d = client.get(f"/convert/jobs/{job_id}/download")
    assert d.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(d.content))
    assert "document.md" in zf.namelist()


def test_sync_rejects_non_zip(client: TestClient) -> None:
    r = client.post(
        "/convert/sync",
        files={"file": ("x.txt", b"not a zip", "text/plain")},
    )
    assert r.status_code == 400
