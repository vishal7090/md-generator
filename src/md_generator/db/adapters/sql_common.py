from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine, Inspector

from md_generator.db.core.base_adapter import BaseAdapter
from md_generator.db.core.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableDetail,
    TableInfo,
)


def _type_str(col: dict[str, Any]) -> str:
    t = col.get("type")
    return str(t) if t is not None else ""


def table_detail_from_inspector(
    insp: Inspector,
    schema: str | None,
    table: TableInfo,
) -> TableDetail:
    name = table.name
    sch = table.schema or schema
    cols_raw = insp.get_columns(name, schema=sch)
    columns: list[ColumnInfo] = []
    for c in sorted(cols_raw, key=lambda x: x["name"]):
        columns.append(
            ColumnInfo(
                name=c["name"],
                data_type=_type_str(c),
                nullable=bool(c.get("nullable", True)),
                default=str(c["default"]) if c.get("default") is not None else None,
                comment=c.get("comment") if isinstance(c.get("comment"), str) else None,
            )
        )
    pk_raw = insp.get_pk_constraint(name, schema=sch)
    pk = tuple(sorted(pk_raw.get("constrained_columns") or ()))

    fks: list[ForeignKeyInfo] = []
    for fk in insp.get_foreign_keys(name, schema=sch):
        fks.append(
            ForeignKeyInfo(
                name=fk.get("name"),
                constrained_columns=tuple(fk.get("constrained_columns") or ()),
                referred_schema=fk.get("referred_schema"),
                referred_table=fk.get("referred_table") or "",
                referred_columns=tuple(fk.get("referred_columns") or ()),
            )
        )
    fks.sort(key=lambda x: (x.name or "", x.referred_table, x.constrained_columns))

    return TableDetail(
        table=table,
        columns=tuple(columns),
        primary_key=pk,
        foreign_keys=tuple(fks),
    )


def indexes_from_inspector(insp: Inspector, schema: str | None, table: TableInfo) -> list[IndexInfo]:
    name = table.name
    sch = table.schema or schema
    out: list[IndexInfo] = []
    for ix in insp.get_indexes(name, schema=sch):
        cols = tuple(ix.get("column_names") or ())
        out.append(
            IndexInfo(
                name=ix.get("name") or "unnamed",
                unique=bool(ix.get("unique", False)),
                columns=cols,
                definition=ix.get("dialect_options", {}).get("definition") if isinstance(ix.get("dialect_options"), dict) else None,
            )
        )
    out.sort(key=lambda i: i.name)
    return out


class SqlAlchemyAdapter(BaseAdapter):
    """Shared helpers for SQLAlchemy-backed adapters."""

    def __init__(self, engine: Engine, schema: str | None, limits: dict[str, Any]) -> None:
        self._engine = engine
        self._schema = schema
        self._limits = limits
        self._insp: Inspector | None = None

    def _inspector(self) -> Inspector:
        if self._insp is None:
            self._insp = inspect(self._engine)
        return self._insp

    def close(self) -> None:
        self._engine.dispose()

    def limits(self) -> dict[str, Any]:
        return dict(self._limits)
