from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from md_generator.db.adapters.factory import create_adapter
from md_generator.db.core.extractor import extract_to_markdown
from md_generator.db.core.run_config import load_run_config


def _make_sample_db(path: Path) -> str:
    uri = f"sqlite:///{path.as_posix()}"
    eng = create_engine(uri)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t1 (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
        conn.execute(
            text(
                "CREATE TABLE t2 (id INTEGER PRIMARY KEY, t1_id INTEGER NOT NULL, "
                "FOREIGN KEY (t1_id) REFERENCES t1(id))"
            )
        )
        conn.execute(text("INSERT INTO t1 (id, name) VALUES (1, 'a')"))
        conn.execute(text("INSERT INTO t2 (id, t1_id) VALUES (1, 1)"))
        conn.execute(text("CREATE VIEW v1 AS SELECT id, name FROM t1"))
        conn.execute(
            text(
                "CREATE TRIGGER tr1 AFTER INSERT ON t1 FOR EACH ROW "
                "BEGIN SELECT 1 WHERE 0; END"
            )
        )
    return uri


def test_create_adapter_sqlite(tmp_path: Path) -> None:
    dbf = tmp_path / "x.db"
    uri = _make_sample_db(dbf)
    a = create_adapter("sqlite", uri, schema="main", database=None, limits={})
    try:
        a.validate_connection()
        tabs = a.get_tables()
        names = {t.name for t in tabs}
        assert "t1" in names and "t2" in names
        t1 = next(t for t in tabs if t.name == "t1")
        detail = a.get_table_detail(t1)
        assert len(detail.columns) == 2
        assert detail.primary_key == ("id",)
        views = a.get_views()
        assert len(views) == 1 and views[0].name == "v1"
        trs = a.get_triggers()
        assert any(t.name == "tr1" for t in trs)
    finally:
        a.close()


def test_sqlite_extract_tables_views_triggers(tmp_path: Path) -> None:
    dbf = tmp_path / "app.db"
    uri = _make_sample_db(dbf)
    out_dir = tmp_path / "md"
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"""
database:
  type: sqlite
  uri: {uri}
  schema: main
output:
  path: {out_dir.as_posix()}
  split_files: true
execution:
  workers: 3
features:
  include: [tables, views, triggers, indexes]
""",
        encoding="utf-8",
    )
    cfg = load_run_config(cfg_path, None)
    extract_to_markdown(cfg)
    assert (out_dir / "README.md").is_file()
    assert (out_dir / "tables" / "main_t1.md").is_file()
    assert (out_dir / "views" / "main.v1.md").is_file()
    assert (out_dir / "triggers" / "main.tr1.md").is_file()
