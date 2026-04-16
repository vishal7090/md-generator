from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from md_generator.url.api.main import app


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """One TestClient for the module so MCP lifespan runs only once."""
    with TestClient(app) as c:
        yield c


def test_convert_sync_zip(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from md_generator.url.fetch import FetchResult

    def fake_fetch(url: str, client, options):
        html = """<!DOCTYPE html><html><head><title>T</title></head>
        <body><h1>Heading</h1><p>Body</p></body></html>"""
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=html,
        )

    monkeypatch.setattr("md_generator.url.convert_impl.fetch_html", fake_fetch)

    r = api_client.post("/convert/sync", json={"url": "https://example.com/"})
    assert r.status_code == 200, r.text
    zf = zipfile.ZipFile(BytesIO(r.content))
    names = zf.namelist()
    assert "document.md" in names


def test_sync_rejects_too_many_urls(api_client: TestClient) -> None:
    r = api_client.post(
        "/convert/sync",
        json={"urls": ["https://a.com/1", "https://a.com/2", "https://a.com/3", "https://a.com/4"]},
    )
    assert r.status_code == 409


def test_jobs_flow(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from md_generator.url.fetch import FetchResult

    def fake_fetch(url: str, client, options):
        html = "<!DOCTYPE html><html><body><p>x</p></body></html>"
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=html,
        )

    monkeypatch.setattr("md_generator.url.convert_impl.fetch_html", fake_fetch)

    r = api_client.post("/convert/jobs", json={"url": "https://example.com/z"})
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    for _ in range(50):
        st = api_client.get(f"/convert/jobs/{job_id}")
        if st.json()["status"] == "done":
            break
    assert st.json()["status"] == "done"
    dl = api_client.get(f"/convert/jobs/{job_id}/download")
    assert dl.status_code == 200
    zf = zipfile.ZipFile(BytesIO(dl.content))
    assert "document.md" in zf.namelist()
