from __future__ import annotations

from md_generator.openapi.normalizers.schema_flatten import collect_schema_refs, merge_all_of


def test_merge_all_of_flattens_named_and_properties() -> None:
    parts = [
        {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
        {"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string"}}},
    ]
    merged = merge_all_of(parts)
    assert merged.get("type") == "object"
    props = merged.get("properties") or {}
    assert "name" in props and "kind" in props
    req = set(merged.get("required") or [])
    assert "name" in req and "kind" in req


def test_collect_schema_refs_sorted() -> None:
    doc = {"a": {"$ref": "#/components/schemas/Z"}, "b": {"$ref": "#/components/schemas/A"}}
    refs = collect_schema_refs(doc)
    assert refs == frozenset(["#/components/schemas/A", "#/components/schemas/Z"])
