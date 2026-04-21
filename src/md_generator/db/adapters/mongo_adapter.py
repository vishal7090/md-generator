from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from md_generator.db.core.base_adapter import BaseAdapter
from md_generator.db.core.models import MongoCollectionInfo, MongoIndexInfo


def _bson_type_name(v: Any) -> str:
    if v is None:
        return "null"
    t = type(v).__name__
    if t == "ObjectId":
        return "ObjectId"
    if t in ("int", "float"):
        return "number"
    if t == "bool":
        return "boolean"
    if t == "str":
        return "string"
    if t == "bytes":
        return "binary"
    if t == "datetime":
        return "datetime"
    if t == "list":
        return "array"
    if t == "dict":
        return "object"
    return t


def _merge_schema(a: Any, b: Any) -> Any:
    """Deterministic merge of inferred type trees."""
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, str) and isinstance(b, str):
        if a == b:
            return a
        return "|".join(sorted({a, b}))
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a) | set(b))
        return {k: _merge_schema(a.get(k), b.get(k)) for k in keys}
    if isinstance(a, list) and isinstance(b, list):
        merged: Any = None
        for x in a + b:
            merged = _merge_schema(merged, x) if merged is not None else x
        return [merged] if merged is not None else []
    if isinstance(a, list):
        return _merge_schema(a[0] if a else None, b)
    if isinstance(b, list):
        return _merge_schema(a, b[0] if b else None)
    return "|".join(sorted({_bson_type_name(a), _bson_type_name(b)}))


def _infer_from_doc(doc: Mapping[str, Any]) -> Any:
    out: dict[str, Any] = {}
    for k in sorted(doc.keys()):
        v = doc[k]
        if isinstance(v, dict):
            out[k] = _infer_from_doc(v)
        elif isinstance(v, list):
            elem: Any = None
            for item in v:
                if isinstance(item, dict):
                    elem = _merge_schema(elem, _infer_from_doc(item))
                else:
                    elem = _merge_schema(elem, _bson_type_name(item))
            out[k] = [elem] if elem is not None else ["null"]
        else:
            out[k] = _bson_type_name(v)
    return out


class MongoAdapter(BaseAdapter):
    db_type = "mongo"

    def __init__(self, uri: str, database: str, limits: dict[str, Any]) -> None:
        from pymongo import MongoClient

        self._client: Any = MongoClient(uri, serverSelectionTimeoutMS=8000)
        self._db = self._client[database]
        self._database_name = database
        self._limits = limits

    def limits(self) -> dict[str, Any]:
        return dict(self._limits)

    def validate_connection(self) -> None:
        self._client.admin.command("ping")

    def close(self) -> None:
        self._client.close()

    def get_collections(self) -> list[MongoCollectionInfo]:
        max_c = int(self._limits.get("max_collections", 500))
        sample_n = int(self._limits.get("sample_size", 50))
        names = sorted(n for n in self._db.list_collection_names() if not n.startswith("system."))[:max_c]
        out: list[MongoCollectionInfo] = []
        for name in names:
            coll = self._db[name]
            schema: Any = None
            count = 0
            try:
                for doc in coll.aggregate([{"$sample": {"size": sample_n}}]):
                    if not isinstance(doc, dict):
                        continue
                    count += 1
                    schema = _merge_schema(schema, _infer_from_doc(doc))
            except Exception:
                try:
                    for doc in coll.find().limit(sample_n):
                        if isinstance(doc, dict):
                            count += 1
                            schema = _merge_schema(schema, _infer_from_doc(doc))
                except Exception:
                    schema = {}
            if schema is None:
                schema = {}
            idxes: list[MongoIndexInfo] = []
            try:
                for spec in coll.list_indexes():
                    raw = dict(spec)
                    iname = str(raw.get("name") or "")
                    unique = bool(raw.get("unique", False))
                    keys_raw = raw.get("key") or {}
                    keys = {str(k): v for k, v in dict(keys_raw).items()}
                    idxes.append(MongoIndexInfo(name=iname, keys=keys, unique=unique))
            except Exception:
                pass
            idxes.sort(key=lambda x: x.name)
            out.append(
                MongoCollectionInfo(
                    name=name,
                    inferred_schema=schema if isinstance(schema, dict) else {"_inferred": schema},
                    indexes=tuple(idxes),
                    sample_size=count,
                )
            )
        return out
