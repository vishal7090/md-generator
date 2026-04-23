from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from md_generator.db.adapters.sql_common import SqlAlchemyAdapter, indexes_from_inspector, table_detail_from_inspector
from md_generator.db.core.models import (
    ClusterInfo,
    IndexInfo,
    PackageInfo,
    PartitionInfo,
    RoutineInfo,
    SequenceInfo,
    TableDetail,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


_ORACLE_DDL_TYPES = frozenset({"FUNCTION", "PROCEDURE", "VIEW", "TRIGGER"})


def _read_ddl_value(val: Any) -> str | None:
    if val is None:
        return None
    if hasattr(val, "read"):
        try:
            return str(val.read())
        except Exception:
            return str(val)
    return str(val)


def _oracle_metadata_ddl(conn: Any, obj_type: str, owner: str, name: str) -> str | None:
    """Optional full DDL when ALL_* text is missing (requires EXECUTE on DBMS_METADATA)."""
    if obj_type not in _ORACLE_DDL_TYPES:
        return None
    try:
        stmt = text("SELECT DBMS_METADATA.GET_DDL(:typ, :oname, :own) AS ddl FROM dual")
        row = conn.execute(
            stmt,
            {"typ": obj_type, "oname": name, "own": owner},
        ).mappings().first()
        if not row:
            return None
        return _read_ddl_value(row.get("ddl"))
    except Exception:
        return None


def _normalize_oracle_uri(uri: str) -> str:
    u = uri.strip()
    if u.startswith("oracle://") and "+oracledb" not in u:
        return u.replace("oracle://", "oracle+oracledb://", 1)
    if u.startswith("jdbc:oracle:thin:"):
        raise ValueError("Use oracle+oracledb:// SQLAlchemy URI, not JDBC string")
    return u


class OracleAdapter(SqlAlchemyAdapter):
    db_type = "oracle"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        eng = create_engine(_normalize_oracle_uri(uri), pool_pre_ping=True, future=True)
        super().__init__(eng, schema.upper(), limits)

    def validate_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM DUAL"))

    def get_tables(self) -> list[TableInfo]:
        owner = self._schema
        q = text(
            """
            SELECT owner, table_name FROM all_tables
            WHERE owner = :owner AND temporary = 'N'
            ORDER BY table_name
            """
        )
        max_t = int(self._limits.get("max_tables", 10_000))
        out: list[TableInfo] = []
        try:
            with self._engine.connect() as conn:
                for i, row in enumerate(conn.execute(q, {"owner": owner}).mappings()):
                    if i >= max_t:
                        break
                    out.append(TableInfo(schema=str(row["owner"]), name=str(row["table_name"])))
        except Exception:
            insp = self._inspector()
            names = insp.get_table_names(schema=owner)
            out = [TableInfo(schema=owner, name=n) for n in sorted(names)[:max_t]]
        return out

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        return table_detail_from_inspector(self._inspector(), self._schema, table)

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return indexes_from_inspector(self._inspector(), self._schema, table)

    def get_views(self) -> list[ViewInfo]:
        q = text(
            """
            SELECT owner, view_name, text AS view_definition
            FROM all_views
            WHERE owner = :owner
            ORDER BY view_name
            """
        )
        out: list[ViewInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    owner = str(row["owner"])
                    vn = str(row["view_name"])
                    vd = row.get("view_definition")
                    text_v = str(vd) if vd is not None else None
                    if not (text_v and text_v.strip()):
                        text_v = _oracle_metadata_ddl(conn, "VIEW", owner, vn)
                    out.append(ViewInfo(schema=owner, name=vn, definition=text_v))
        except Exception:
            return []
        return out

    def _source_agg(self, object_type: str) -> dict[tuple[str, str], str]:
        q = text(
            """
            SELECT owner, name, type, line, text
            FROM all_source
            WHERE owner = :owner AND type = :otype
            ORDER BY name, line
            """
        )
        chunks: dict[tuple[str, str], list[str]] = {}
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema, "otype": object_type}).mappings():
                    key = (str(row["owner"]), str(row["name"]))
                    chunks.setdefault(key, []).append(str(row["text"]) if row.get("text") is not None else "")
        except Exception:
            return {}
        return {k: "".join(v) for k, v in sorted(chunks.items())}

    def get_functions(self) -> list[RoutineInfo]:
        q = text(
            """
            SELECT owner, object_name FROM all_objects
            WHERE owner = :owner AND object_type = 'FUNCTION'
            ORDER BY object_name
            """
        )
        sources = self._source_agg("FUNCTION")
        out: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    owner, name = str(row["owner"]), str(row["object_name"])
                    src = sources.get((owner, name))
                    if not (src and src.strip()):
                        src = _oracle_metadata_ddl(conn, "FUNCTION", owner, name)
                    out.append(
                        RoutineInfo(
                            kind="FUNCTION",
                            schema=owner,
                            name=name,
                            language="PL/SQL",
                            definition=src,
                        )
                    )
        except Exception:
            return []
        return out

    def get_procedures(self) -> list[RoutineInfo]:
        q = text(
            """
            SELECT owner, object_name FROM all_objects
            WHERE owner = :owner AND object_type = 'PROCEDURE'
            ORDER BY object_name
            """
        )
        sources_proc = self._source_agg("PROCEDURE")
        out: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    owner, name = str(row["owner"]), str(row["object_name"])
                    src = sources_proc.get((owner, name))
                    if not (src and src.strip()):
                        src = _oracle_metadata_ddl(conn, "PROCEDURE", owner, name)
                    out.append(
                        RoutineInfo(
                            kind="PROCEDURE",
                            schema=owner,
                            name=name,
                            language="PL/SQL",
                            definition=src,
                        )
                    )
        except Exception:
            return []
        return out

    def get_triggers(self) -> list[TriggerInfo]:
        q = text(
            """
            SELECT owner, trigger_name, table_owner, table_name, triggering_event,
                   trigger_type, status, trigger_body
            FROM all_triggers
            WHERE owner = :owner
            ORDER BY table_name, trigger_name
            """
        )
        out: list[TriggerInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    owner = str(row["owner"])
                    tname = str(row["trigger_name"])
                    body = row.get("trigger_body")
                    bstr = str(body) if body is not None else None
                    if not (bstr and bstr.strip()):
                        bstr = _oracle_metadata_ddl(conn, "TRIGGER", owner, tname)
                    out.append(
                        TriggerInfo(
                            schema=owner,
                            name=tname,
                            table_schema=str(row["table_owner"]),
                            table_name=str(row["table_name"]),
                            definition=bstr,
                            timing=str(row["trigger_type"]) if row.get("trigger_type") else None,
                            events=str(row["triggering_event"]) if row.get("triggering_event") else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_sequences(self) -> list[SequenceInfo]:
        q = text(
            """
            SELECT sequence_owner, sequence_name FROM all_sequences
            WHERE sequence_owner = :owner
            ORDER BY sequence_name
            """
        )
        out: list[SequenceInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    out.append(
                        SequenceInfo(
                            schema=str(row["sequence_owner"]),
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
            SELECT table_owner, table_name, partition_name, partitioning_type, high_value
            FROM all_tab_partitions
            WHERE table_owner = :owner
            ORDER BY table_name, partition_name
            """
        )
        out: list[PartitionInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    hv = row.get("high_value")
                    out.append(
                        PartitionInfo(
                            schema=str(row["table_owner"]),
                            parent_table=str(row["table_name"]),
                            name=str(row["partition_name"]),
                            method=str(row["partitioning_type"]) if row.get("partitioning_type") else None,
                            expression=str(hv) if hv is not None else None,
                        )
                    )
        except Exception:
            return []
        return out

    def get_packages(self) -> list[PackageInfo]:
        spec_map = self._source_agg("PACKAGE")
        body_map = self._source_agg("PACKAGE BODY")
        names = sorted({n for _, n in spec_map.keys()} | {n for _, n in body_map.keys()})
        owner = self._schema
        return [
            PackageInfo(
                schema=owner,
                name=n,
                spec_source=spec_map.get((owner, n)),
                body_source=body_map.get((owner, n)),
            )
            for n in names
        ]

    def get_clusters(self) -> list[ClusterInfo]:
        q = text(
            """
            SELECT owner, cluster_name, tablespace_name, cluster_type
            FROM all_clusters
            WHERE owner = :owner
            ORDER BY cluster_name
            """
        )
        out: list[ClusterInfo] = []
        try:
            with self._engine.connect() as conn:
                for row in conn.execute(q, {"owner": self._schema}).mappings():
                    out.append(
                        ClusterInfo(
                            schema=str(row["owner"]),
                            name=str(row["cluster_name"]),
                            details={
                                "tablespace": str(row["tablespace_name"]) if row.get("tablespace_name") else None,
                                "cluster_type": str(row["cluster_type"]) if row.get("cluster_type") else None,
                            },
                        )
                    )
        except Exception:
            return []
        return out
