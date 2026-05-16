from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from md_generator.db.adapters.sql_common import SqlAlchemyAdapter, indexes_from_inspector, table_detail_from_inspector
from md_generator.db.core.models import (
    ColumnInfo,
    DependencyEdge,
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    SequenceInfo,
    SynonymInfo,
    TableDetail,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


def _normalize_mssql_uri(uri: str) -> str:
    u = uri.strip()
    if u.startswith("sqlserver://"):
        u = u.replace("sqlserver://", "mssql+pyodbc://", 1)
    elif u.startswith("mssql://") and "+pyodbc" not in u:
        u = u.replace("mssql://", "mssql+pyodbc://", 1)
    return u


class SqlServerAdapter(SqlAlchemyAdapter):
    db_type = "mssql"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        eng = create_engine(_normalize_mssql_uri(uri), pool_pre_ping=True, future=True)
        super().__init__(eng, schema, limits)
        self._schema = schema
        self._table_comments: dict[str, str] = {}
        self._column_comments: dict[tuple[str, str], str] = {}
        self._routine_comments: dict[tuple[str, str], str] = {}
        self._load_extended_properties()

    def validate_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def list_schemas(self) -> list[str]:
        q = text(
            """
            SELECT name FROM sys.schemas
            WHERE name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest')
            ORDER BY name
            """
        )
        try:
            with self._engine.connect() as conn:
                return [str(r[0]) for r in conn.execute(q)]
        except Exception:
            return []

    def _load_extended_properties(self) -> None:
        q = text(
            """
            SELECT
                o.name AS object_name,
                c.name AS column_name,
                CAST(ep.value AS nvarchar(max)) AS descr
            FROM sys.extended_properties ep
            INNER JOIN sys.objects o ON ep.major_id = o.object_id
            LEFT JOIN sys.columns c
                ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
            INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
            WHERE ep.name = N'MS_Description'
              AND s.name = :schema
            """
        )
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    obj = str(row["object_name"])
                    col = row.get("column_name")
                    descr = str(row["descr"]) if row.get("descr") is not None else ""
                    if col is None:
                        self._table_comments[obj] = descr
                    else:
                        self._column_comments[(obj, str(col))] = descr
        except Exception:
            pass
        q2 = text(
            """
            SELECT o.name, CAST(ep.value AS nvarchar(max)) AS descr
            FROM sys.extended_properties ep
            INNER JOIN sys.objects o ON ep.major_id = o.object_id
            INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
            WHERE ep.name = N'MS_Description' AND ep.minor_id = 0
              AND s.name = :schema
              AND o.type IN ('P', 'FN', 'IF', 'TF')
            """
        )
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q2, {"schema": self._schema}).mappings():
                    self._routine_comments[(str(row["name"]), "")] = str(row["descr"] or "")
        except Exception:
            pass

    def get_tables(self) -> list[TableInfo]:
        insp = self._inspector()
        names = insp.get_table_names(schema=self._schema)
        max_t = int(self._limits.get("max_tables", 10_000))
        out = [
            TableInfo(
                schema=self._schema,
                name=n,
                comment=self._table_comments.get(n),
            )
            for n in sorted(names)[:max_t]
        ]
        return out

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        detail = table_detail_from_inspector(self._inspector(), self._schema, table)
        cols: list[ColumnInfo] = []
        for c in detail.columns:
            comment = self._column_comments.get((table.name, c.name)) or c.comment
            cols.append(
                ColumnInfo(
                    name=c.name,
                    data_type=c.data_type,
                    nullable=c.nullable,
                    default=c.default,
                    comment=comment,
                )
            )
        tbl = TableInfo(
            schema=table.schema,
            name=table.name,
            comment=self._table_comments.get(table.name) or table.comment,
        )
        return TableDetail(
            table=tbl,
            columns=tuple(cols),
            primary_key=detail.primary_key,
            foreign_keys=detail.foreign_keys,
        )

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return indexes_from_inspector(self._inspector(), self._schema, table)

    def get_views(self) -> list[ViewInfo]:
        q = text(
            """
            SELECT v.name, m.definition
            FROM sys.views v
            INNER JOIN sys.sql_modules m ON v.object_id = m.object_id
            INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
            WHERE s.name = :schema
            ORDER BY v.name
            """
        )
        out: list[ViewInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        ViewInfo(
                            schema=self._schema,
                            name=str(row["name"]),
                            definition=str(row["definition"]) if row.get("definition") else None,
                        )
                    )
        except Exception:
            return []
        return out

    def _routines(self, type_letter: str, label: str) -> list[RoutineInfo]:
        q = text(
            """
            SELECT o.name, m.definition, o.type_desc
            FROM sys.objects o
            INNER JOIN sys.sql_modules m ON o.object_id = m.object_id
            INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
            WHERE s.name = :schema AND o.type = :typ
            ORDER BY o.name
            """
        )
        out: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema, "typ": type_letter}).mappings():
                    nm = str(row["name"])
                    out.append(
                        RoutineInfo(
                            kind=label,
                            schema=self._schema,
                            name=nm,
                            language="TSQL",
                            definition=str(row["definition"]) if row.get("definition") else None,
                            comment=self._routine_comments.get((nm, "")),
                        )
                    )
        except Exception:
            return []
        return out

    def get_functions(self) -> list[RoutineInfo]:
        out: list[RoutineInfo] = []
        for t, label in (("FN", "FUNCTION"), ("IF", "FUNCTION"), ("TF", "FUNCTION")):
            out.extend(self._routines(t, label))
        return sorted(out, key=lambda r: r.name)

    def get_procedures(self) -> list[RoutineInfo]:
        return self._routines("P", "PROCEDURE")

    def get_triggers(self) -> list[TriggerInfo]:
        q = text(
            """
            SELECT t.name, OBJECT_SCHEMA_NAME(t.parent_id) AS table_schema,
                   OBJECT_NAME(t.parent_id) AS table_name,
                   OBJECT_DEFINITION(t.object_id) AS definition
            FROM sys.triggers t
            WHERE OBJECT_SCHEMA_NAME(t.parent_id) = :schema
            ORDER BY table_name, t.name
            """
        )
        out: list[TriggerInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        TriggerInfo(
                            schema=self._schema,
                            name=str(row["name"]),
                            table_schema=str(row["table_schema"]),
                            table_name=str(row["table_name"]),
                            definition=str(row["definition"]) if row.get("definition") else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_sequences(self) -> list[SequenceInfo]:
        q = text(
            """
            SELECT name FROM sys.sequences s
            INNER JOIN sys.schemas sch ON s.schema_id = sch.schema_id
            WHERE sch.name = :schema
            ORDER BY name
            """
        )
        out: list[SequenceInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(SequenceInfo(schema=self._schema, name=str(row["name"]), details={}))
        except Exception:
            return []
        return out

    def get_partitions(self) -> list[PartitionInfo]:
        return []

    def get_synonyms(self) -> list[SynonymInfo]:
        q = text(
            """
            SELECT name, base_object_name
            FROM sys.synonyms syn
            INNER JOIN sys.schemas s ON syn.schema_id = s.schema_id
            WHERE s.name = :schema
            ORDER BY name
            """
        )
        out: list[SynonymInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        SynonymInfo(
                            schema=self._schema,
                            name=str(row["name"]),
                            base_object=str(row["base_object_name"]),
                        )
                    )
        except Exception:
            return []
        return out

    def get_dependencies(self) -> list[DependencyEdge]:
        q = text(
            """
            SELECT
                OBJECT_SCHEMA_NAME(d.referencing_id) AS referencing_schema,
                OBJECT_NAME(d.referencing_id) AS referencing_name,
                o_ref.type_desc AS referencing_kind,
                OBJECT_SCHEMA_NAME(d.referenced_id) AS referenced_schema,
                OBJECT_NAME(d.referenced_id) AS referenced_name,
                o_refd.type_desc AS referenced_kind
            FROM sys.sql_expression_dependencies d
            INNER JOIN sys.objects o_ref ON d.referencing_id = o_ref.object_id
            INNER JOIN sys.objects o_refd ON d.referenced_id = o_refd.object_id
            WHERE OBJECT_SCHEMA_NAME(d.referencing_id) = :schema
            ORDER BY referencing_name, referenced_name
            """
        )
        out: list[DependencyEdge] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"schema": self._schema}).mappings():
                    out.append(
                        DependencyEdge(
                            referencing_schema=str(row["referencing_schema"]),
                            referencing_name=str(row["referencing_name"]),
                            referencing_kind=str(row["referencing_kind"]),
                            referenced_schema=str(row["referenced_schema"] or ""),
                            referenced_name=str(row["referenced_name"]),
                            referenced_kind=str(row["referenced_kind"]),
                        )
                    )
        except Exception:
            return []
        return out
