from __future__ import annotations

from typing import Any


def sample_from_schema(
    schema: dict[str, Any] | None,
    *,
    invalid_enum: bool = False,
    omit_keys: frozenset[str] | None = None,
) -> Any:
    """Build a deterministic example value from a JSON Schema fragment (subset)."""
    if schema is None:
        return None
    if not isinstance(schema, dict):
        return None
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        choices = list(schema["enum"])
        choices.sort(key=lambda x: (type(x).__name__, str(x)))
        if invalid_enum:
            return "__invalid_enum__"
        return choices[0]
    if "const" in schema:
        return schema["const"]
    if "oneOf" in schema and isinstance(schema["oneOf"], list) and schema["oneOf"]:
        first = schema["oneOf"][0]
        if isinstance(first, dict):
            return sample_from_schema(first, invalid_enum=invalid_enum, omit_keys=omit_keys)
    if "anyOf" in schema and isinstance(schema["anyOf"], list) and schema["anyOf"]:
        first = schema["anyOf"][0]
        if isinstance(first, dict):
            return sample_from_schema(first, invalid_enum=invalid_enum, omit_keys=omit_keys)
    typ = schema.get("type")
    if typ == "object" or ("properties" in schema and isinstance(schema.get("properties"), dict)):
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        req = schema.get("required")
        req_list = [str(x) for x in req] if isinstance(req, list) else []
        req_list.sort()
        out: dict[str, Any] = {}
        keys = sorted(props.keys())
        for k in keys:
            if omit_keys is not None and k in omit_keys:
                continue
            sub = props[k]
            if isinstance(sub, dict):
                out[k] = sample_from_schema(sub, invalid_enum=invalid_enum, omit_keys=None)
        for k in req_list:
            if k not in out and k in props and isinstance(props[k], dict):
                out[k] = sample_from_schema(props[k], invalid_enum=invalid_enum, omit_keys=None)
        return out
    if typ == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [sample_from_schema(items, invalid_enum=invalid_enum, omit_keys=omit_keys)]
        return []
    if typ == "string":
        fmt = str(schema.get("format") or "")
        if fmt == "date":
            return "2000-01-01"
        if fmt == "date-time":
            return "2000-01-01T00:00:00Z"
        return "string"
    if typ == "integer":
        return 0
    if typ == "number":
        return 0.0
    if typ == "boolean":
        return True
    if typ == "null":
        return None
    return {}
