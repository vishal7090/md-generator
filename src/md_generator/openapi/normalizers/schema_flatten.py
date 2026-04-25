from __future__ import annotations

import copy
from typing import Any


def _sorted_unique_strs(items: list[str]) -> list[str]:
    return sorted({str(x) for x in items if x is not None and str(x) != ""})


def merge_all_of(parts: list[Any]) -> dict[str, Any]:
    """Merge JSON Schema ``allOf`` branches into one object (deterministic, best-effort)."""
    merged: dict[str, Any] = {"type": "object"}
    props: dict[str, Any] = {}
    required: set[str] = set()
    descriptions: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if "allOf" in part and isinstance(part["allOf"], list):
            inner = merge_all_of(part["allOf"])
            _merge_schema_fragment(merged, props, required, descriptions, inner)
        else:
            _merge_schema_fragment(merged, props, required, descriptions, part)
    if props:
        merged["properties"] = {k: props[k] for k in sorted(props.keys())}
    if required:
        merged["required"] = sorted(required)
    if descriptions:
        merged["description"] = "\n".join(descriptions)
    return merged


def _merge_schema_fragment(
    merged: dict[str, Any],
    props: dict[str, Any],
    required: set[str],
    descriptions: list[str],
    frag: dict[str, Any],
) -> None:
    t = frag.get("type")
    if isinstance(t, str):
        merged["type"] = t
    if isinstance(frag.get("description"), str) and frag["description"].strip():
        descriptions.append(frag["description"].strip())
    p = frag.get("properties")
    if isinstance(p, dict):
        for k in sorted(p.keys()):
            props[k] = copy.deepcopy(p[k])
    r = frag.get("required")
    if isinstance(r, list):
        for x in r:
            if isinstance(x, str):
                required.add(x)
    for k, v in frag.items():
        if k in ("type", "description", "properties", "required", "allOf"):
            continue
        if k not in merged or merged[k] == {}:
            merged[k] = copy.deepcopy(v)


def flatten_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a documentation-oriented schema without ``allOf`` when mergeable."""
    if schema is None:
        return None
    if not isinstance(schema, dict):
        return None
    s = copy.deepcopy(schema)
    if "allOf" in s and isinstance(s["allOf"], list):
        merged = merge_all_of(s["allOf"])
        rest = {k: v for k, v in s.items() if k != "allOf"}
        out = {**merged, **rest}
        if "allOf" in out:
            del out["allOf"]
        return _normalize_composition(out)
    return _normalize_composition(s)


def _normalize_composition(s: dict[str, Any]) -> dict[str, Any]:
    """Attach stable metadata for ``oneOf`` / ``anyOf`` without resolving branches."""
    out = copy.deepcopy(s)
    for key in ("oneOf", "anyOf"):
        if key in out and isinstance(out[key], list):
            branches = [flatten_schema(b) if isinstance(b, dict) else b for b in out[key]]
            out[key] = [b for b in branches if b is not None]
    return out


def collect_schema_refs(obj: Any) -> frozenset[str]:
    found: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            ref = x.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                found.add(ref)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for it in x:
                walk(it)

    walk(obj)
    return frozenset(sorted(found))
