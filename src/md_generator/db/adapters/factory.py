from __future__ import annotations

from typing import Any

from sqlalchemy.engine.url import make_url

from md_generator.db.adapters.mongo_adapter import MongoAdapter
from md_generator.db.adapters.mysql_adapter import MysqlAdapter
from md_generator.db.adapters.oracle_adapter import OracleAdapter
from md_generator.db.adapters.postgres_adapter import PostgresAdapter
from md_generator.db.adapters.sqlite_adapter import SqliteAdapter
from md_generator.db.core.base_adapter import BaseAdapter


def create_adapter(
    db_type: str,
    uri: str,
    *,
    schema: str | None = None,
    database: str | None = None,
    limits: dict[str, Any] | None = None,
) -> BaseAdapter:
    lim = dict(limits or {})
    t = db_type.lower().strip()
    if t in ("postgres", "postgresql"):
        sch = schema or "public"
        return PostgresAdapter(uri, sch, lim)
    if t in ("mysql", "mariadb"):
        sch = schema or make_url(uri).database
        if not sch:
            raise ValueError("MySQL requires database in URI path or --schema")
        return MysqlAdapter(uri, sch, lim)
    if t in ("oracle",):
        if not schema:
            raise ValueError("Oracle requires schema (owner) in config or --schema")
        return OracleAdapter(uri, schema, lim)
    if t in ("mongo", "mongodb"):
        if not database:
            raise ValueError("MongoDB requires database name in config or --database")
        return MongoAdapter(uri, database, lim)
    if t in ("sqlite",):
        sch = (schema or "main").strip()
        if sch.lower() == "public":
            sch = "main"
        return SqliteAdapter(uri, sch, lim)
    raise ValueError(f"Unsupported database type: {db_type!r}")
