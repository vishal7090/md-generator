from __future__ import annotations

from typing import Any

from md_generator.db.core.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableDetail,
    TableInfo,
)


def _is_user_table(name: str) -> bool:
    if not name:
        return False
    upper = name.upper()
    return not upper.startswith("MSYS") and not upper.startswith("~")


def list_user_tables(cursor) -> list[str]:
    names: list[str] = []
    for row in cursor.tables(tableType="TABLE"):
        n = getattr(row, "table_name", None) or row[2]
        if n and _is_user_table(str(n)):
            names.append(str(n))
    return sorted(set(names))


def table_detail_from_odbc(cursor, catalog_schema: str, table: TableInfo) -> TableDetail:
    name = table.name
    columns: list[ColumnInfo] = []
    try:
        col_rows = list(cursor.columns(table=name))
    except UnicodeDecodeError:
        col_rows = []
    for row in col_rows:
        col_name = getattr(row, "column_name", None) or row[3]
        if not col_name:
            continue
        nullable_raw = getattr(row, "nullable", None)
        if nullable_raw is None and len(row) > 10:
            nullable_raw = row[10]
        nullable = True if nullable_raw in (1, True, "YES") else False
        type_name = getattr(row, "type_name", None) or (row[5] if len(row) > 5 else "")
        default = getattr(row, "column_def", None)
        if default is None and len(row) > 12:
            default = row[12]
        columns.append(
            ColumnInfo(
                name=str(col_name),
                data_type=str(type_name or ""),
                nullable=nullable,
                default=str(default) if default is not None else None,
            )
        )
    columns.sort(key=lambda c: c.name)

    pk: tuple[str, ...] = ()
    try:
        pk_rows = list(cursor.primaryKeys(table=name))
        pk_rows.sort(key=lambda r: getattr(r, "key_seq", None) or r[4] or 0)
        pk = tuple(
            str(getattr(r, "column_name", None) or r[3])
            for r in pk_rows
            if getattr(r, "column_name", None) or (len(r) > 3 and r[3])
        )
    except Exception:
        pk = ()

    fks: list[ForeignKeyInfo] = []
    try:
        fk_rows = cursor.foreignKeys(table=name)
    except Exception:
        fk_rows = ()
    for row in fk_rows:
        fk_name = getattr(row, "fk_name", None) or (row[11] if len(row) > 11 else None)
        fk_col = getattr(row, "fkcolumn_name", None) or (row[7] if len(row) > 7 else None)
        pk_table = getattr(row, "pktable_name", None) or (row[2] if len(row) > 2 else "")
        pk_col = getattr(row, "pkcolumn_name", None) or (row[3] if len(row) > 3 else None)
        if fk_col and pk_table and pk_col:
            fks.append(
                ForeignKeyInfo(
                    name=str(fk_name) if fk_name else None,
                    constrained_columns=(str(fk_col),),
                    referred_schema=None,
                    referred_table=str(pk_table),
                    referred_columns=(str(pk_col),),
                )
            )
    fks.sort(key=lambda x: (x.name or "", x.referred_table, x.constrained_columns))

    return TableDetail(
        table=table,
        columns=tuple(columns),
        primary_key=pk,
        foreign_keys=tuple(fks),
    )


def indexes_from_odbc(cursor, table: TableInfo) -> list[IndexInfo]:
    by_name: dict[str, dict[str, Any]] = {}
    for row in cursor.statistics(table=table.name):
        ix_name = getattr(row, "index_name", None) or (row[5] if len(row) > 5 else None)
        if not ix_name:
            continue
        ix_name = str(ix_name)
        non_unique = getattr(row, "non_unique", None)
        if non_unique is None and len(row) > 3:
            non_unique = row[3]
        col = getattr(row, "column_name", None) or (row[8] if len(row) > 8 else None)
        ord_pos = getattr(row, "ordinal_position", None) or (row[7] if len(row) > 7 else 0)
        entry = by_name.setdefault(ix_name, {"unique": non_unique == 0, "cols": {}})
        if col:
            entry["cols"][int(ord_pos or 0)] = str(col)

    out: list[IndexInfo] = []
    for name, data in sorted(by_name.items()):
        cols = tuple(data["cols"][k] for k in sorted(data["cols"]))
        if cols:
            out.append(IndexInfo(name=name, unique=bool(data["unique"]), columns=cols))
    return out
