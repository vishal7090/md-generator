from __future__ import annotations

from dataclasses import dataclass

from md_generator.db.core.models import ForeignKeyInfo, TableDetail


TableKey = tuple[str, str]  # (schema, table_name)


@dataclass(frozen=True)
class FKEdge:
    from_schema: str
    from_table: str
    to_schema: str
    to_table: str
    fk_name: str | None
    constrained_columns: tuple[str, ...]
    referred_columns: tuple[str, ...]

    @property
    def from_key(self) -> TableKey:
        return (self.from_schema, self.from_table)

    @property
    def to_key(self) -> TableKey:
        return (self.to_schema, self.to_table)

    def sort_tuple(self) -> tuple:
        return (
            self.from_schema,
            self.from_table,
            self.fk_name or "",
            self.to_schema,
            self.to_table,
            self.constrained_columns,
            self.referred_columns,
        )


def table_key(detail: TableDetail) -> TableKey:
    t = detail.table
    return (t.schema, t.name)


def collect_fk_edges(details: list[TableDetail]) -> tuple[FKEdge, ...]:
    """Deterministic edge list from introspected table details."""
    edges: list[FKEdge] = []
    for d in sorted(details, key=table_key):
        fs, ft = table_key(d)
        for fk in sorted(d.foreign_keys, key=lambda x: (x.name or "", x.referred_table, x.constrained_columns)):
            ts = fk.referred_schema if fk.referred_schema else fs
            tt = fk.referred_table
            edges.append(
                FKEdge(
                    from_schema=fs,
                    from_table=ft,
                    to_schema=ts,
                    to_table=tt,
                    fk_name=fk.name,
                    constrained_columns=tuple(fk.constrained_columns),
                    referred_columns=tuple(fk.referred_columns),
                )
            )
    return tuple(sorted(edges, key=lambda e: e.sort_tuple()))
