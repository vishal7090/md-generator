from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus

_ACCESS_DRIVER_PREFERENCES = (
    "Microsoft Access Driver (*.mdb, *.accdb)",
    "Microsoft Access Driver (*.mdb)",
)


def list_odbc_drivers() -> list[str]:
    try:
        import pyodbc

        return list(pyodbc.drivers())
    except Exception:
        return []


def resolve_access_driver() -> str:
    installed = list_odbc_drivers()
    lower = {d.lower(): d for d in installed}
    for pref in _ACCESS_DRIVER_PREFERENCES:
        if pref.lower() in lower:
            return lower[pref.lower()]
    for d in installed:
        if "access" in d.lower():
            return d
    raise RuntimeError(
        "No Microsoft Access ODBC driver found. Installed drivers: "
        + (", ".join(installed) if installed else "(none)")
        + ". Install Microsoft Access Database Engine (ACE) on Windows."
    )


def access_file_extension(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in (".mdb", ".accdb"):
        raise ValueError(f"Access database must be .mdb or .accdb, got {path.suffix!r}")
    return ext


def access_odbc_connect_string(path: Path, *, driver: str | None = None) -> str:
    access_file_extension(path.resolve())
    drv = driver or resolve_access_driver()
    dbq = str(path.resolve())
    return f"DRIVER={{{drv}}};DBQ={dbq};"


def access_sqlalchemy_uri(path: Path, *, driver: str | None = None) -> str:
    """SQLAlchemy URI via generic ``mssql+pyodbc`` + ``odbc_connect`` (Access driver in string)."""
    cs = access_odbc_connect_string(path, driver=driver)
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(cs)}"


def odbc_connect_string_from_sqlalchemy_uri(uri: str) -> str:
    if "odbc_connect=" not in uri:
        raise ValueError("Access URI must include odbc_connect= query parameter")
    part = uri.split("odbc_connect=", 1)[1]
    return unquote_plus(part.split("&", 1)[0])


def create_access_engine(uri: str):
    """Engine for Access via pyodbc without MSSQL ``schema_name()`` probe on connect."""
    import pyodbc
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    cs = odbc_connect_string_from_sqlalchemy_uri(uri)

    def creator():
        conn = pyodbc.connect(cs)
        for sql_type, enc in (
            (pyodbc.SQL_CHAR, "cp1252"),
            (pyodbc.SQL_WCHAR, "utf-16le"),
            (pyodbc.SQL_WMETADATA, "utf-16le"),
        ):
            try:
                conn.setdecoding(sql_type, encoding=enc, errors="replace")
            except Exception:
                pass
        return conn

    engine = create_engine(
        "mssql+pyodbc://",
        creator=creator,
        poolclass=NullPool,
        future=True,
    )
    dialect = engine.dialect
    dialect.default_schema_name = "dbo"
    dialect._get_default_schema_name = lambda _connection: "dbo"  # type: ignore[method-assign]

    def initialize(connection):
        # Access ODBC is not SQL Server; skip MSSQL version/extended-property probes.
        dialect.default_schema_name = "dbo"
        dialect.server_version_info = (16, 0, 0)
        dialect.supports_comments = False
        dialect._supports_nvarchar_max = False

    dialect.initialize = initialize  # type: ignore[method-assign]
    return engine


def is_access_filename(name: str) -> bool:
    return bool(re.search(r"\.(mdb|accdb)$", name, re.I))
