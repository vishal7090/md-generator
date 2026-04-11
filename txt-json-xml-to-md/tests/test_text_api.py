from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_api_sync_and_jobs() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    sample_json = FIXTURES / "sample.json"
    assert sample_json.is_file()
    from fastapi.testclient import TestClient

    from md_generator.text.api.main import app

    data = sample_json.read_bytes()
    with TestClient(app) as client:
        r = client.post(
            "/convert/sync",
            files={"file": ("sample.json", data, "application/json")},
            params={"include_source_block": "true"},
        )
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")
        with zipfile.ZipFile(io.BytesIO(r.content), "r") as zf:
            md = zf.read("document.md").decode("utf-8")
        assert "## User" in md

        r2 = client.post(
            "/convert/jobs",
            files={"file": ("sample.json", data, "application/json")},
        )
        assert r2.status_code == 200, r2.text
        jid = r2.json()["job_id"]

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
