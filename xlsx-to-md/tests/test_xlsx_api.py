from __future__ import annotations

import io
import zipfile
import pytest

pytest.importorskip("fastapi")

from openpyxl import Workbook
from starlette.testclient import TestClient

from md_generator.xlsx.api.app import app


def _xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["A"])
    ws.append([1])
    wb.save(buf)
    return buf.getvalue()


def test_convert_sync_zip() -> None:
    client = TestClient(app)
    files = {"file": ("t.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/convert/sync", files=files)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/zip")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "t.md" in names or any(n.endswith(".md") for n in names)
    assert "conversion_log.txt" in names


def test_convert_sync_rejects_bad_ext() -> None:
    client = TestClient(app)
    files = {"file": ("n.txt", b"x", "text/plain")}
    r = client.post("/convert/sync", files=files)
    assert r.status_code == 400


def test_job_lifecycle() -> None:
    client = TestClient(app)
    files = {"file": ("job.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/convert/jobs", files=files)
    assert r.status_code == 200
    jid = r.json()["id"]
    for _ in range(50):
        st = client.get(f"/convert/jobs/{jid}")
        assert st.status_code == 200
        if st.json()["status"] == "done":
            break
    else:
        pytest.fail("job did not complete")
    dl = client.get(f"/convert/jobs/{jid}/download")
    assert dl.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    assert "conversion_log.txt" in zf.namelist()
