from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from md_generator.db.adapters.sql_common import SqlAlchemyAdapter, indexes_from_inspector, table_detail_from_inspector
from md_generator.db.core.models import IndexInfo, TableDetail, TableInfo, TriggerInfo, ViewInfo

_ATTACH_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_sqlite_uri(uri: str) -> str:
    u = uri.strip()
    if u.startswith("sqlite://") and "+pysqlite" not in u and "+aiosqlite" not in u:
        return u.replace("sqlite://", "sqlite+pysqlite://", 1)
    return u


def _sqlite_master_expr(schema: str) -> str:
    """Return SQL fragment for sqlite_master of the given catalog (``main`` or attach name)."""
    s = (schema or "main").strip()
    if s.lower() == "main":
        return "sqlite_master"
    if not _ATTACH_NAME.fullmatch(s):
        raise ValueError(f"Invalid SQLite catalog/schema name: {schema!r} (use main or an attach alias)")
    return f'"{s}".sqlite_master'


class SqliteAdapter(SqlAlchemyAdapter):
    db_type = "sqlite"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        eng = create_engine(
            _normalize_sqlite_uri(uri),
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
            future=True,
        )
        super().__init__(eng, schema, limits)

    def validate_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def get_tables(self) -> list[TableInfo]:
        insp = self._inspector()
        sch = self._schema or "main"
        names = insp.get_table_names(schema=sch)
        max_t = int(self._limits.get("max_tables", 10_000))
        out = [TableInfo(schema=sch, name=n) for n in sorted(names)[:max_t]]
        return out

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        return table_detail_from_inspector(self._inspector(), self._schema, table)

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return indexes_from_inspector(self._inspector(), self._schema, table)

    def get_views(self) -> list[ViewInfo]:
        sch = self._schema or "main"
        master = _sqlite_master_expr(sch)
        q = text(f"SELECT name, sql FROM {master} WHERE type = 'view' AND sql IS NOT NULL ORDER BY name")
        out: list[ViewInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q).mappings():
                    out.append(
                        ViewInfo(
                            schema=sch,
                            name=str(row["name"]),
                            definition=str(row["sql"]) if row.get("sql") is not None else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_triggers(self) -> list[TriggerInfo]:
        sch = self._schema or "main"
        master = _sqlite_master_expr(sch)
        q = text(
            f"SELECT name, tbl_name, sql FROM {master} "
            "WHERE type = 'trigger' AND sql IS NOT NULL ORDER BY tbl_name, name"
        )
        out: list[TriggerInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q).mappings():
                    sql = row.get("sql")
                    out.append(
                        TriggerInfo(
                            schema=sch,
                            name=str(row["name"]),
                            table_schema=sch,
                            table_name=str(row["tbl_name"]),
                            definition=str(sql) if sql is not None else None,
                            timing=None,
                            events=None,
                        )
                    )
        except Exception:
            return []
        return out
