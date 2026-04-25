from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_openapi.yaml"


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    from md_generator.openapi.api.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


def test_generate_returns_zip(api_client: TestClient) -> None:
    body = _FIXTURE.read_bytes()
    r = api_client.post(
        "/openapi-to-md/generate",
        files={"file": ("minimal_openapi.yaml", body, "application/x-yaml")},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "README.md" in names
    assert "endpoints/get__pets.md" in names
