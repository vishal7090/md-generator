from __future__ import annotations

from fastapi.testclient import TestClient

from md_generator.log.api.main import app


def test_health() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
