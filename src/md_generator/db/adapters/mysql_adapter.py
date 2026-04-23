from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from md_generator.db.adapters.sql_common import SqlAlchemyAdapter, indexes_from_inspector, table_detail_from_inspector
from md_generator.db.core.models import (
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    SequenceInfo,
    TableDetail,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


def _normalize_mysql_uri(uri: str) -> str:
    u = uri.strip()
    if u.startswith("mysql://") and "+pymysql" not in u:
        return u.replace("mysql://", "mysql+pymysql://", 1)
    return u


def _quote_ident(name: str) -> str:
    """Backtick-quote a MySQL identifier (names come from the server, not end users)."""
    return "`" + name.replace("`", "``") + "`"


def _row_dict_lower(row: Any) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in dict(row).items()}


def _pick_create_clause(row: Any) -> str | None:
    d = _row_dict_lower(row)
    for k, v in d.items():
        if "create" in k and v is not None:
            return str(v)
    return None


def _canonical_schema(conn: Any, schema: str) -> str:
    """Match configured database name to server catalog casing (Windows / lower_case_table_names)."""
    row = conn.execute(
        text(
            "SELECT SCHEMA_NAME FROM information_schema.schemata "
            "WHERE SCHEMA_NAME = :s LIMIT 1"
        ),
        {"s": schema},
    ).fetchone()
    if row:
        return str(row[0])
    row2 = conn.execute(
        text(
            "SELECT SCHEMA_NAME FROM information_schema.schemata "
            "WHERE LOWER(SCHEMA_NAME) = LOWER(:s) LIMIT 1"
        ),
        {"s": schema},
    ).fetchone()
    return str(row2[0]) if row2 else schema


def _session_use_db(conn: Any, sch: str) -> None:
    """Set session default database so INFORMATION_SCHEMA ... = DATABASE() matches target schema."""
    conn.execute(text(f"USE {_quote_ident(sch)}"))


class MysqlAdapter(SqlAlchemyAdapter):
    db_type = "mysql"

    def __init__(self, uri: str, schema: str, limits: dict[str, Any]) -> None:
        eng = create_engine(_normalize_mysql_uri(uri), pool_pre_ping=True, future=True)
        super().__init__(eng, schema, limits)

    def validate_connection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def get_tables(self) -> list[TableInfo]:
        insp = self._inspector()
        with self._engine.connect() as c:
            sch = _canonical_schema(c, self._schema)
        names = insp.get_table_names(schema=sch)
        max_t = int(self._limits.get("max_tables", 10_000))
        out = [TableInfo(schema=sch, name=n) for n in sorted(names)[:max_t]]
        return out

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        return table_detail_from_inspector(self._inspector(), self._schema, table)

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return indexes_from_inspector(self._inspector(), self._schema, table)

    def get_views(self) -> list[ViewInfo]:
        """
        Native-style flow (PyMySQL via SQLAlchemy):
        1) USE canonical database
        2) TABLE_NAME, VIEW_DEFINITION from INFORMATION_SCHEMA.VIEWS where TABLE_SCHEMA = DATABASE()
        3) Union view names from INFORMATION_SCHEMA.TABLES (VIEW)
        4) If definition missing / useless -> SHOW CREATE VIEW
        """
        out: list[ViewInfo] = []
        try:
            with self._engine.connect() as conn:
                sch = _canonical_schema(conn, self._schema)
                _session_use_db(conn, sch)
                q_isc = text(
                    """
                    SELECT table_name, view_definition
                    FROM information_schema.views
                    WHERE table_schema = DATABASE()
                    ORDER BY table_name
                    """
                )
                by_name: dict[str, str | None] = {}
                for row in conn.execute(q_isc).mappings():
                    d = _row_dict_lower(row)
                    tn = str(d["table_name"])
                    vd = d.get("view_definition")
                    s = str(vd).strip() if vd is not None else ""
                    by_name[tn] = s if s else None
                q_tbl = text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_type = 'VIEW'
                    ORDER BY table_name
                    """
                )
                for row in conn.execute(q_tbl).mappings():
                    tn = str(_row_dict_lower(row)["table_name"])
                    by_name.setdefault(tn, None)
                for vn in sorted(by_name.keys()):
                    defn = by_name.get(vn)
                    if not defn:
                        try:
                            show_sql = f"SHOW CREATE VIEW {_quote_ident(sch)}.{_quote_ident(vn)}"
                            r = conn.execute(text(show_sql)).mappings().first()
                            if r:
                                defn = _pick_create_clause(r)
                        except Exception:
                            pass
                    if not defn:
                        try:
                            r2 = conn.execute(
                                text(
                                    "SELECT view_definition FROM information_schema.views "
                                    "WHERE table_schema = DATABASE() AND table_name = :vn LIMIT 1"
                                ),
                                {"vn": vn},
                            ).mappings().first()
                            if r2:
                                r2d = _row_dict_lower(r2)
                                if r2d.get("view_definition") is not None:
                                    vd2 = str(r2d["view_definition"]).strip()
                                    defn = vd2 or None
                        except Exception:
                            pass
                    out.append(ViewInfo(schema=sch, name=vn, definition=defn))
        except Exception:
            return []
        return out

    def _routine_rows_information_schema_db(
        self, conn: Any, rtype: str
    ) -> list[tuple[str, str | None, str | None]]:
        """ROUTINE_NAME, language, ROUTINE_DEFINITION using ROUTINE_SCHEMA = DATABASE() after USE."""
        q = text(
            """
            SELECT routine_name, external_language, routine_definition
            FROM information_schema.routines
            WHERE routine_schema = DATABASE() AND routine_type = :rtype
            ORDER BY routine_name
            """
        )
        rows: list[tuple[str, str | None, str | None]] = []
        for row in conn.execute(q, {"rtype": rtype}).mappings():
            d = _row_dict_lower(row)
            rd = d.get("routine_definition")
            body = str(rd).strip() if rd is not None else ""
            rows.append(
                (
                    str(d["routine_name"]),
                    str(d["external_language"]) if d.get("external_language") else None,
                    body if body else None,
                )
            )
        return rows

    def _routine_names_show_status_db(self, conn: Any, rtype: str) -> list[str]:
        """SHOW {FUNCTION|PROCEDURE} STATUS WHERE Db = DATABASE() after USE."""
        show = "SHOW FUNCTION STATUS" if rtype == "FUNCTION" else "SHOW PROCEDURE STATUS"
        names: list[str] = []
        try:
            for row in conn.execute(text(f"{show} WHERE `Db` = DATABASE()")).mappings():
                d = _row_dict_lower(row)
                name = str(d.get("name") or "")
                if name:
                    names.append(name)
        except Exception:
            return []
        return names

    def _routines(self, rtype: str) -> list[RoutineInfo]:
        """
        Native-style flow:
        1) USE canonical database
        2) ROUTINE_NAME, ROUTINE_DEFINITION from INFORMATION_SCHEMA.ROUTINES where ROUTINE_SCHEMA = DATABASE()
        3) Merge names from SHOW FUNCTION|PROCEDURE STATUS WHERE Db = DATABASE()
        4) If definition missing -> SHOW CREATE FUNCTION|PROCEDURE
        5) Final fallback: re-read routine_definition from INFORMATION_SCHEMA (same session)
        """
        label = "FUNCTION" if rtype == "FUNCTION" else "PROCEDURE"
        sch_cfg = self._schema
        out: list[RoutineInfo] = []
        try:
            with self._engine.connect() as conn:
                sch = _canonical_schema(conn, sch_cfg)
                _session_use_db(conn, sch)
                by_name: dict[str, tuple[str | None, str | None]] = {}
                for rn, lang, body in self._routine_rows_information_schema_db(conn, rtype):
                    by_name[rn] = (lang, body)
                for rn in self._routine_names_show_status_db(conn, rtype):
                    by_name.setdefault(rn, (None, None))
                for rn in sorted(by_name.keys()):
                    lang, body = by_name[rn]
                    defn = body
                    if not defn:
                        try:
                            show_kw = "SHOW CREATE FUNCTION" if rtype == "FUNCTION" else "SHOW CREATE PROCEDURE"
                            show_sql = f"{show_kw} {_quote_ident(sch)}.{_quote_ident(rn)}"
                            r = conn.execute(text(show_sql)).mappings().first()
                            if r:
                                defn = _pick_create_clause(r)
                        except Exception:
                            pass
                    if not defn:
                        try:
                            r2 = conn.execute(
                                text(
                                    "SELECT routine_definition AS body FROM information_schema.routines "
                                    "WHERE routine_schema = DATABASE() AND routine_name = :rn "
                                    "AND routine_type = :rt LIMIT 1"
                                ),
                                {"rn": rn, "rt": rtype},
                            ).mappings().first()
                            if r2:
                                r2d = _row_dict_lower(r2)
                                if r2d.get("body") is not None:
                                    b = str(r2d["body"]).strip()
                                    defn = b or None
                        except Exception:
                            pass
                    out.append(
                        RoutineInfo(
                            kind=label,
                            schema=sch,
                            name=rn,
                            language=lang,
                            definition=defn,
                        )
                    )
        except Exception:
            return []
        return out

    def get_functions(self) -> list[RoutineInfo]:
        return self._routines("FUNCTION")

    def get_procedures(self) -> list[RoutineInfo]:
        return self._routines("PROCEDURE")

    def get_triggers(self) -> list[TriggerInfo]:
        """After USE db, SHOW TRIGGERS uses current database (same as DATABASE())."""
        out: list[TriggerInfo] = []
        try:
            with self._engine.connect() as conn:
                sch = _canonical_schema(conn, self._schema)
                _session_use_db(conn, sch)
                for row in conn.execute(text("SHOW TRIGGERS")).mappings():
                    d = _row_dict_lower(row)
                    tname = str(d.get("trigger") or "")
                    tbl = str(d.get("table") or "")
                    events = str(d.get("event") or "")
                    timing = str(d.get("timing") or "")
                    stmt = d.get("statement")
                    stmt_s = str(stmt) if stmt is not None else None
                    out.append(
                        TriggerInfo(
                            schema=sch,
                            name=tname,
                            table_schema=sch,
                            table_name=tbl,
                            definition=stmt_s,
                            timing=timing or None,
                            events=events or None,
                        )
                    )
        except Exception:
            return []
        out.sort(key=lambda tr: (tr.table_name, tr.name))
        return out

    def get_sequences(self) -> list[SequenceInfo]:
        return []

    def get_partitions(self) -> list[PartitionInfo]:
        return []
