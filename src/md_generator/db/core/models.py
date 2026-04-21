from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


FEATURES = frozenset(
    {
        "tables",
        "views",
        "indexes",
        "procedures",
        "functions",
        "triggers",
        "sequences",
        "partitions",
        "oracle_packages",
        "oracle_clusters",
        "mongodb_collections",
        "erd",
    }
)


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    default: str | None = None
    comment: str | None = None


@dataclass(frozen=True)
class ForeignKeyInfo:
    name: str | None
    constrained_columns: tuple[str, ...]
    referred_schema: str | None
    referred_table: str
    referred_columns: tuple[str, ...]


@dataclass(frozen=True)
class IndexInfo:
    name: str
    unique: bool
    columns: tuple[str, ...]
    definition: str | None = None


@dataclass(frozen=True)
class TableInfo:
    schema: str
    name: str
    comment: str | None = None


@dataclass(frozen=True)
class TableDetail:
    table: TableInfo
    columns: tuple[ColumnInfo, ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[ForeignKeyInfo, ...]


@dataclass(frozen=True)
class ViewInfo:
    schema: str
    name: str
    definition: str | None


@dataclass(frozen=True)
class RoutineInfo:
    kind: str  # FUNCTION | PROCEDURE
    schema: str
    name: str
    language: str | None
    definition: str | None


@dataclass(frozen=True)
class TriggerInfo:
    schema: str
    name: str
    table_schema: str
    table_name: str
    definition: str | None
    timing: str | None = None
    events: str | None = None


@dataclass(frozen=True)
class SequenceInfo:
    schema: str
    name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PartitionInfo:
    schema: str
    parent_table: str
    name: str
    method: str | None = None
    expression: str | None = None


@dataclass(frozen=True)
class PackageInfo:
    schema: str
    name: str
    spec_source: str | None = None
    body_source: str | None = None


@dataclass(frozen=True)
class ClusterInfo:
    schema: str
    name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MongoIndexInfo:
    name: str
    keys: dict[str, Any]
    unique: bool = False


@dataclass(frozen=True)
class MongoCollectionInfo:
    name: str
    inferred_schema: dict[str, Any]
    indexes: tuple[MongoIndexInfo, ...]
    sample_size: int


@dataclass(frozen=True)
class RunMetadata:
    db_type: str
    uri_display: str  # redacted
    schema: str | None
    database: str | None  # Mongo
    included_features: tuple[str, ...]
    limits: dict[str, Any]
    generated_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    erd_artifacts: tuple[str, ...] = ()
    erd_note: str | None = None
    erd_engine: str | None = None  # graphviz | mermaid_py | mermaid_text
