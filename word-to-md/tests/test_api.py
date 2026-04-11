from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from tests.conftest import minimal_docx_bytes


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("WORD_TO_MD_TEMP_DIR", str(tmp_path))
    monkeypatch.setenv("WORD_TO_MD_MAX_UPLOAD_MB", "50")
    monkeypatch.setenv("WORD_TO_MD_MAX_SYNC_UPLOAD_MB", "50")
    # Fresh import picks up env
    import importlib

    import api.main as api_main

    importlib.reload(api_main)
    with TestClient(api_main.app) as c:
        yield c


def test_convert_sync_zip(client: TestClient) -> None:
    docx = minimal_docx_bytes()
    r = client.post(
        "/convert/sync",
        files={"file": ("test.docx", io.BytesIO(docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/zip")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "document.md" in names
    assert "conversion_log.txt" in names
    md = zf.read("document.md").decode("utf-8")
    assert "HelloWordToMd" in md


def test_convert_sync_413_when_over_sync_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORD_TO_MD_MAX_SYNC_UPLOAD_MB", "0.00001")
    import importlib

    import api.main as api_main

    importlib.reload(api_main)
    with TestClient(api_main.app) as c:
        docx = minimal_docx_bytes()
        r = c.post(
            "/convert/sync",
            files={"file": ("big.docx", io.BytesIO(docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert r.status_code == 413


def test_job_flow(client: TestClient) -> None:
    docx = minimal_docx_bytes()
    r = client.post(
        "/convert/jobs",
        files={"file": ("job.docx", io.BytesIO(docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    import time

    for _ in range(50):
        st = client.get(f"/convert/jobs/{job_id}")
        assert st.status_code == 200
        if st.json()["status"] == "done":
            break
        if st.json()["status"] == "error":
            pytest.fail(str(st.json()))
        time.sleep(0.05)
    else:
        pytest.fail("job did not complete")
    dl = client.get(f"/convert/jobs/{job_id}/download")
    assert dl.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    assert "document.md" in zf.namelist()
