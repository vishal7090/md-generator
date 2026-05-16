from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote_plus

from sqlalchemy import text

from md_generator.db.adapters.access_odbc import (
    access_sqlalchemy_uri,
    create_access_engine,
    resolve_access_driver,
)
from md_generator.db.adapters.access_introspect import (
    indexes_from_odbc,
    list_user_tables,
    table_detail_from_odbc,
)
from md_generator.db.adapters.sql_common import SqlAlchemyAdapter
from md_generator.db.core.models import IndexInfo, RoutineInfo, TableDetail, TableInfo, TriggerInfo, ViewInfo


def _path_from_access_uri(uri: str) -> Path | None:
    if "odbc_connect=" not in uri:
        return None
    part = uri.split("odbc_connect=", 1)[1]
    cs = unquote_plus(part.split("&", 1)[0])
    for piece in cs.split(";"):
        if piece.upper().startswith("DBQ="):
            return Path(piece[4:])
    return None


class AccessAdapter(SqlAlchemyAdapter):
    db_type = "access"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        path = _path_from_access_uri(uri)
        if path is not None and path.is_file():
            norm_uri = access_sqlalchemy_uri(path)
        elif uri.startswith("mssql+pyodbc://") and "odbc_connect=" in uri:
            norm_uri = uri
        elif uri.startswith("access+pyodbc://"):
            norm_uri = uri.replace("access+pyodbc://", "mssql+pyodbc://", 1)
        else:
            norm_uri = uri
        eng = create_access_engine(norm_uri)
        super().__init__(eng, schema, limits)
        self._schema = schema or "main"
        self._action_queries: list[RoutineInfo] = []

    def _odbc_cursor(self):
        raw = self._engine.raw_connection()
        return raw, raw.cursor()

    def validate_connection(self) -> None:
        resolve_access_driver()
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def list_schemas(self) -> list[str]:
        return ["main"]

    def get_tables(self) -> list[TableInfo]:
        raw, cur = self._odbc_cursor()
        try:
            names = list_user_tables(cur)
        finally:
            cur.close()
            raw.close()
        max_t = int(self._limits.get("max_tables", 10_000))
        return [TableInfo(schema=self._schema, name=n) for n in names[:max_t]]

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        raw, cur = self._odbc_cursor()
        try:
            return table_detail_from_odbc(cur, self._schema, table)
        finally:
            cur.close()
            raw.close()

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        raw, cur = self._odbc_cursor()
        try:
            return indexes_from_odbc(cur, table)
        finally:
            cur.close()
            raw.close()

    def _msys_queries(self) -> list[ViewInfo]:
        """Saved SELECT queries (QueryDefs) as views; action queries as procedures."""
        views: list[ViewInfo] = []
        procs: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT Name, SQL, Type
                        FROM MSysObjects
                        WHERE Type = 5 AND Flags = 0
                        ORDER BY Name
                        """
                    )
                ).fetchall()
        except Exception:
            return views
        for row in rows:
            name = str(row[0])
            sql = str(row[1]) if row[1] is not None else None
            typ = int(row[2]) if row[2] is not None else 0
            if sql and sql.strip().upper().startswith("SELECT"):
                views.append(ViewInfo(schema=self._schema, name=name, definition=sql))
            else:
                procs.append(
                    RoutineInfo(
                        kind="QUERY",
                        schema=self._schema,
                        name=name,
                        language="Access",
                        definition=sql,
                    )
                )
        self._action_queries = procs
        return views

    def get_views(self) -> list[ViewInfo]:
        self._action_queries: list[RoutineInfo] = []
        views = self._msys_queries()
        if views:
            return views
        return views

    def get_procedures(self) -> list[RoutineInfo]:
        if not hasattr(self, "_action_queries"):
            self.get_views()
        return getattr(self, "_action_queries", [])

    def get_functions(self) -> list[RoutineInfo]:
        return []

    def get_triggers(self) -> list[TriggerInfo]:
        return []
