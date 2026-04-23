from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from md_generator.db.adapters.sql_common import SqlAlchemyAdapter, indexes_from_inspector, table_detail_from_inspector
from md_generator.db.core.models import (
    ClusterInfo,
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    SequenceInfo,
    TableDetail,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


def _normalize_postgres_uri(uri: str) -> str:
    u = uri.strip()
    if u.startswith("postgresql://") and "+psycopg2" not in u and "+asyncpg" not in u:
        return u.replace("postgresql://", "postgresql+psycopg2://", 1)
    if u.startswith("postgres://"):
        return u.replace("postgres://", "postgresql+psycopg2://", 1)
    return u


class PostgresAdapter(SqlAlchemyAdapter):
    db_type = "postgres"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        eng = create_engine(_normalize_postgres_uri(uri), pool_pre_ping=True, future=True)
        super().__init__(eng, schema, limits)
        self._schema = schema

    def validate_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def get_tables(self) -> list[TableInfo]:
        insp = self._inspector()
        names = insp.get_table_names(schema=self._schema)
        max_t = int(self._limits.get("max_tables", 10_000))
        out = [TableInfo(schema=self._schema, name=n) for n in sorted(names)[:max_t]]
        return out

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        return table_detail_from_inspector(self._inspector(), self._schema, table)

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return indexes_from_inspector(self._inspector(), self._schema, table)

    def get_views(self) -> list[ViewInfo]:
        """Prefer pg_views / pg_matviews (full definitions); fall back to information_schema."""
        out: list[ViewInfo] = []
        sch = self._schema
        q_pg = text(
            """
            SELECT schemaname AS table_schema, viewname AS table_name, definition AS view_definition
            FROM pg_catalog.pg_views
            WHERE schemaname = :schema
            ORDER BY viewname
            """
        )
        q_mv = text(
            """
            SELECT schemaname AS table_schema, matviewname AS table_name, definition AS view_definition
            FROM pg_catalog.pg_matviews
            WHERE schemaname = :schema
            ORDER BY matviewname
            """
        )
        q_is = text(
            """
            SELECT table_schema, table_name, view_definition
            FROM information_schema.views
            WHERE table_schema = :schema
            ORDER BY table_schema, table_name
            """
        )
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q_pg, {"schema": sch}).mappings():
                    vd = row.get("view_definition")
                    out.append(
                        ViewInfo(
                            schema=str(row["table_schema"]),
                            name=str(row["table_name"]),
                            definition=str(vd) if vd is not None else None,
                        )
                    )
                try:
                    for row in conn.execute(q_mv, {"schema": sch}).mappings():
                        vd = row.get("view_definition")
                        out.append(
                            ViewInfo(
                                schema=str(row["table_schema"]),
                                name=str(row["table_name"]),
                                definition=str(vd) if vd is not None else None,
                            )
                        )
                except Exception:
                    pass
                if not out:
                    for row in conn.execute(q_is, {"schema": sch}).mappings():
                        vd = row.get("view_definition")
                        out.append(
                            ViewInfo(
                                schema=str(row["table_schema"]),
                                name=str(row["table_name"]),
                                definition=str(vd) if vd is not None else None,
                            )
                        )
        except Exception:
            return []
        return out

    def _routines(self, kind: str) -> list[RoutineInfo]:
        """kind: 'f' function, 'p' procedure (PostgreSQL 11+)."""
        q = text(
            """
            SELECT n.nspname AS schema_name, p.proname AS name, l.lanname AS language,
                   pg_get_functiondef(p.oid) AS definition
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            JOIN pg_language l ON p.prolang = l.oid
            WHERE n.nspname = :schema AND p.prokind = :kind
            ORDER BY n.nspname, p.proname
            """
        )
        label = "FUNCTION" if kind == "f" else "PROCEDURE"
        out: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema, "kind": kind}).mappings():
                    out.append(
                        RoutineInfo(
                            kind=label,
                            schema=str(row["schema_name"]),
                            name=str(row["name"]),
                            language=str(row["language"]) if row.get("language") else None,
                            definition=str(row["definition"]) if row.get("definition") else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_functions(self) -> list[RoutineInfo]:
        return self._routines("f")

    def get_procedures(self) -> list[RoutineInfo]:
        return self._routines("p")

    def get_triggers(self) -> list[TriggerInfo]:
        """Prefer pg_get_triggerdef (authoritative DDL); fall back to information_schema."""
        sch = self._schema
        q_pg = text(
            """
            SELECT n.nspname AS trigger_schema,
                   t.tgname AS trigger_name,
                   n.nspname AS table_schema,
                   c.relname AS event_object_table,
                   pg_get_triggerdef(t.oid, true) AS definition
            FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE NOT t.tgisinternal
              AND n.nspname = :schema
            ORDER BY c.relname, t.tgname
            """
        )
        out: list[TriggerInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q_pg, {"schema": sch}).mappings():
                    defn = row.get("definition")
                    out.append(
                        TriggerInfo(
                            schema=str(row["trigger_schema"]),
                            name=str(row["trigger_name"]),
                            table_schema=str(row["table_schema"]),
                            table_name=str(row["event_object_table"]),
                            definition=str(defn) if defn is not None else None,
                            timing=None,
                            events=None,
                        )
                    )
                if out:
                    return out
                q_is = text(
                    """
                    SELECT trigger_schema, trigger_name, event_object_schema, event_object_table,
                           action_timing, event_manipulation, action_statement
                    FROM information_schema.triggers
                    WHERE trigger_schema = :schema
                    ORDER BY trigger_schema, trigger_name, event_manipulation
                    """
                )
                merged: dict[tuple[str, str, str, str, str, str | None], list[str]] = {}
                for row in conn.execute(q_is, {"schema": sch}).mappings():
                    key = (
                        str(row["trigger_schema"]),
                        str(row["trigger_name"]),
                        str(row["event_object_schema"]),
                        str(row["event_object_table"]),
                        str(row["action_timing"]) if row.get("action_timing") else "",
                        str(row["action_statement"]) if row.get("action_statement") else None,
                    )
                    ev = str(row["event_manipulation"]) if row.get("event_manipulation") else ""
                    merged.setdefault(key, []).append(ev)
                for k, evs in sorted(merged.items()):
                    ts, tn, es, et, timing, stmt = k
                    out.append(
                        TriggerInfo(
                            schema=ts,
                            name=tn,
                            table_schema=es,
                            table_name=et,
                            definition=stmt,
                            timing=timing or None,
                            events=", ".join(sorted({e for e in evs if e})),
                        )
                    )
        except Exception:
            return []
        return out

    def get_sequences(self) -> list[SequenceInfo]:
        q = text(
            """
            SELECT sequence_schema, sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema = :schema
            ORDER BY sequence_schema, sequence_name
            """
        )
        out: list[SequenceInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        SequenceInfo(
                            schema=str(row["sequence_schema"]),
                            name=str(row["sequence_name"]),
                            details={},
                        )
                    )
        except Exception:
            return []
        return out

    def get_partitions(self) -> list[PartitionInfo]:
        q = text(
            """
            SELECT n.nspname AS schema_name,
                   c_parent.relname AS parent_table,
                   c_child.relname AS partition_name,
                   pg_get_expr(c_child.relpartbound, c_child.oid, true) AS bound_expr
            FROM pg_inherit i
            JOIN pg_class c_child ON c_child.oid = i.inhrelid
            JOIN pg_class c_parent ON c_parent.oid = i.inhparent
            JOIN pg_namespace n ON n.oid = c_child.relnamespace
            WHERE n.nspname = :schema AND c_child.relispartition
            ORDER BY parent_table, partition_name
            """
        )
        out: list[PartitionInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        PartitionInfo(
                            schema=str(row["schema_name"]),
                            parent_table=str(row["parent_table"]),
                            name=str(row["partition_name"]),
                            method="partition",
                            expression=str(row["bound_expr"]) if row.get("bound_expr") else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_packages(self) -> list[PackageInfo]:
        return []

    def get_clusters(self) -> list[ClusterInfo]:
        return []
