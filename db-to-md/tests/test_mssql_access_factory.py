from __future__ import annotations

import pytest

from md_generator.db.adapters.access_odbc import is_access_filename, resolve_access_driver
from md_generator.db.adapters.factory import create_adapter
from md_generator.db.core.export_manifest import ExportManifestBuilder
from md_generator.db.core.models import RunMetadata
from md_generator.db.core.run_config import RunConfig


pytest.importorskip("pyodbc")


def test_create_adapter_mssql() -> None:
    a = create_adapter(
        "mssql",
        "mssql+pyodbc://user:pass@localhost:1433/db?driver=ODBC+Driver+18+for+SQL+Server",
        schema="dbo",
        limits={},
    )
    assert a.db_type == "mssql"
    a.close()


def test_create_adapter_access_uri() -> None:
    from md_generator.db.adapters.access_odbc import access_sqlalchemy_uri
    from pathlib import Path

    # Explicit driver avoids requiring ACE/ODBC on CI (Linux runners have no Access driver).
    fake_driver = "Microsoft Access Driver (*.mdb, *.accdb)"
    uri = access_sqlalchemy_uri(Path("C:/data/test.accdb"), driver=fake_driver)
    assert "odbc_connect=" in uri
    assert "test.accdb" in uri
    a = create_adapter("access", uri, schema="main", limits={})
    assert a.db_type == "access"
    a.close()


def test_is_access_filename() -> None:
    assert is_access_filename("x.accdb")
    assert is_access_filename("x.MDB")
    assert not is_access_filename("x.sqlite")


def test_export_manifest_builder(tmp_path) -> None:
    b = ExportManifestBuilder()
    b.bump("tables", 2)
    p = tmp_path / "README.md"
    p.write_text("# x\n", encoding="utf-8")
    b.add_file(p, tmp_path)
    meta = RunMetadata(
        db_type="sqlite",
        uri_display="sqlite:///t.db",
        schema="main",
        database=None,
        included_features=("tables",),
        limits={},
    )
    cfg = RunConfig(db_type="sqlite", uri="sqlite:///t.db", schema="main")
    out = b.write(tmp_path, cfg, meta)
    assert out.is_file()
    assert "tables" in out.read_text(encoding="utf-8")


@pytest.mark.skipif(
    not resolve_access_driver,
    reason="requires Access ODBC driver",
)
def test_resolve_access_driver_when_installed() -> None:
    try:
        name = resolve_access_driver()
        assert "access" in name.lower()
    except RuntimeError:
        pytest.skip("no Access ODBC driver on this host")
