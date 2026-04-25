from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

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


def test_create_sqlite_file_job_writes_db(tmp_path: Path) -> None:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    dbp = Path(name)
    try:
        uri = f"sqlite:///{dbp.as_posix()}"
        eng = create_engine(uri)
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE z (id INTEGER PRIMARY KEY)"))
        eng.dispose()
        blob = dbp.read_bytes()
    finally:
        dbp.unlink(missing_ok=True)

    jm = JobManager(in_memory=True, workspace_root=tmp_path / "jw")
    try:
        tpl = RunConfig(
            db_type="sqlite",
            uri="sqlite:///placeholder",
            schema="main",
            output_path=Path("."),
            include=frozenset(["tables"]),
        )
        rec = jm.create_sqlite_file_job(blob, tpl)
        up = Path(rec.workspace) / "upload.sqlite"
        assert up.is_file()
        loaded = jm.load_config(rec.job_id)
        assert loaded is not None
        assert "upload.sqlite" in loaded.uri
        assert loaded.db_type == "sqlite"
    finally:
        jm.close()
