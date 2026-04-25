from __future__ import annotations

import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def _sqlite_bytes() -> bytes:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    try:
        uri = f"sqlite:///{path.as_posix()}"
        eng = create_engine(uri)
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE q (id INTEGER PRIMARY KEY)"))
        eng.dispose()
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def db_api_client() -> TestClient:
    """One app lifespan per module (MCP session manager is single-use per process)."""
    root = Path(tempfile.mkdtemp())
    os.environ["DB_TO_MD_JOB_SQLITE_PATH"] = str(root / "jobs.sqlite")
    os.environ["DB_TO_MD_JOB_WORKSPACE_ROOT"] = str(root / "ws")
    from md_generator.db.api.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def test_run_sqlite_upload_sync_returns_zip(db_api_client: TestClient) -> None:
    body = _sqlite_bytes()
    cfg = {"features": {"include": ["tables"], "exclude": []}}
    resp = db_api_client.post(
        "/db-to-md/run/sqlite",
        files={"file": ("test.sqlite", io.BytesIO(body), "application/octet-stream")},
        data={"config": json.dumps(cfg)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/zip")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "README.md" in names
    assert any(n.startswith("tables/") for n in names)


def test_run_sqlite_upload_rejects_non_sqlite(db_api_client: TestClient) -> None:
    resp = db_api_client.post(
        "/db-to-md/run/sqlite",
        files={"file": ("x.txt", io.BytesIO(b"not a database"), "text/plain")},
    )
    assert resp.status_code == 400


def test_job_sqlite_upload_roundtrip(db_api_client: TestClient) -> None:
    body = _sqlite_bytes()
    cfg = {"features": {"include": ["tables"], "exclude": []}}
    resp = db_api_client.post(
        "/db-to-md/job/sqlite",
        files={"file": ("test.sqlite", io.BytesIO(body), "application/octet-stream")},
        data={"config": json.dumps(cfg)},
    )
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        st = db_api_client.get(f"/db-to-md/job/{job_id}")
        assert st.status_code == 200
        if st.json().get("status") == "COMPLETED":
            break
        if st.json().get("status") == "FAILED":
            pytest.fail(st.json().get("error", "job failed"))
        time.sleep(0.15)
    else:
        pytest.fail("job did not complete in time")
    dl = db_api_client.get(f"/db-to-md/job/{job_id}/download")
    assert dl.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    assert "README.md" in zf.namelist()
