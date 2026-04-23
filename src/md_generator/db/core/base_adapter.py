from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from md_generator.db.core.models import (
    ClusterInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    MongoCollectionInfo,
    PackageInfo,
    PartitionInfo,
    RoutineInfo,
    SequenceInfo,
    TableDetail,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


class BaseAdapter(ABC):
    """Introspection adapter; unsupported features return empty containers."""

    db_type: str

    @abstractmethod
    def validate_connection(self) -> None:
        """Raise if the database is unreachable."""

    @abstractmethod
    def close(self) -> None:
        """Release connections/clients."""

    def get_tables(self) -> list[TableInfo]:
        return []

    def get_table_detail(self, table: TableInfo) -> TableDetail:
        raise NotImplementedError

    def get_indexes(self, table: TableInfo) -> list[IndexInfo]:
        return []

    def get_views(self) -> list[ViewInfo]:
        return []

    def get_functions(self) -> list[RoutineInfo]:
        return []

    def get_procedures(self) -> list[RoutineInfo]:
        return []

    def get_triggers(self) -> list[TriggerInfo]:
        return []

    def get_sequences(self) -> list[SequenceInfo]:
        return []

    def get_partitions(self) -> list[PartitionInfo]:
        return []

    def get_packages(self) -> list[PackageInfo]:
        return []

    def get_clusters(self) -> list[ClusterInfo]:
        return []

    def get_collections(self) -> list[MongoCollectionInfo]:
        return []

    def limits(self) -> dict[str, Any]:
        return {}
