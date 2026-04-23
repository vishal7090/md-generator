from __future__ import annotations

from pathlib import Path

from md_generator.db.core.job_manager import JobManager
from md_generator.db.core.run_config import RunConfig


def test_job_create_and_load_roundtrip() -> None:
    jm = JobManager(in_memory=True)
    try:
        cfg = RunConfig(
            db_type="postgres",
            uri="postgresql://u:p@127.0.0.1:59999/ghost",
            schema="public",
            output_path=Path("docs"),
        )
        rec = jm.create_job(cfg)
        loaded = jm.load_config(rec.job_id)
        assert loaded is not None
        assert loaded.uri == cfg.uri
        assert loaded.db_type == "postgres"
        got = jm.get(rec.job_id)
        assert got is not None
        assert got.status == "PENDING"
        assert loaded.erd.max_tables == 100
        assert loaded.erd.scope == "full"
    finally:
        jm.close()
