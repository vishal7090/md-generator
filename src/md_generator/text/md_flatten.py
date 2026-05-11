from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, List, Mapping

from md_generator.text.md_emit_json import _slug, _title_key


def _scalar_repr(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return str(v)


def flatten_structure(obj: Any, prefix: str = "") -> dict[str, str]:
    """Dot/bracket paths (e.g. ``user.name``, ``items[0].id``) → string leaf values."""
    out: dict[str, str] = {}
    if not isinstance(obj, (Mapping, list, tuple)):
        key = prefix if prefix else "value"
        out[key] = _scalar_repr(obj)
        return out
    if isinstance(obj, Mapping):
        if not obj:
            if prefix:
                out[prefix] = "{}"
            return out
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten_structure(v, key))
        return out
    if isinstance(obj, (list, tuple)):
        if not obj:
            if prefix:
                out[prefix] = "[]"
            return out
        for i, item in enumerate(obj):
            key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            out.update(flatten_structure(item, key))
        return out
    if prefix:
        out[prefix] = _scalar_repr(obj)
    return out


def _to_plain_mapping(obj: Any) -> Any:
    if isinstance(obj, OrderedDict):
        return {k: _to_plain_mapping(v) for k, v in obj.items()}
    if isinstance(obj, Mapping):
        return {k: _to_plain_mapping(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain_mapping(x) for x in obj]
    return obj


def parse_xml_to_ordered_dict(xml_text: str) -> Any:
    try:
        import xmltodict
    except ImportError as e:
        raise ValueError(
            "Flattened XML requires xmltodict. Install: pip install 'mdengine[text]' (or pip install xmltodict)."
        ) from e
    parsed = xmltodict.parse(xml_text)
    return _to_plain_mapping(parsed)


def _group_title(group: str) -> str:
    s = re.sub(r"\[(\d+)\]", r" \1 ", group)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return _title_key(s) if s else group


def flattened_to_markdown(
    flat: dict[str, str],
    raw_text: str,
    *,
    include_source_block: bool,
    generate_toc: bool,
    fence_lang: str,
) -> str:
    """Group flat paths by first segment; remainder as bold labels (headings from path roots)."""
    from collections import defaultdict

    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path in sorted(flat.keys()):
        if "." in path:
            head, rest = path.split(".", 1)
        else:
            head, rest = path, ""
        groups[head].append((rest, flat[path]))

    out: List[str] = []
    toc: List[tuple[str, str]] = []

    for group in sorted(groups.keys()):
        title = _group_title(group)
        out.append("")
        out.append(f"## {title}")
        toc.append((title, _slug(title)))
        for rest, val in sorted(groups[group], key=lambda x: x[0]):
            if rest:
                out.append(f"- **{rest}:** {val}")
            else:
                out.append(f"- {val}")

    body = "\n".join(out)
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")

    prefix = ""
    if generate_toc and toc:
        lines = ["## Table of contents", ""]
        for title, slug in toc:
            lines.append(f"- [{title}](#{slug})")
        lines.append("")
        prefix = "\n".join(lines)

    chunks: List[str] = []
    if prefix.strip():
        chunks.append(prefix.rstrip())
    if body.strip():
        chunks.append(body.strip())
    if include_source_block:
        chunks.append(f"```{fence_lang}")
        chunks.append(raw_text.rstrip())
        chunks.append("```")
    return "\n\n".join(chunks).strip() + "\n"


def json_flatten_to_markdown(
    obj: Any,
    raw_text: str,
    *,
    include_source_block: bool,
    generate_toc: bool,
) -> str:
    flat = flatten_structure(obj)
    return flattened_to_markdown(
        flat,
        raw_text,
        include_source_block=include_source_block,
        generate_toc=generate_toc,
        fence_lang="json",
    )


def xml_flatten_to_markdown(
    xml_text: str,
    raw_text: str,
    *,
    include_source_block: bool,
    generate_toc: bool,
) -> str:
    tree = parse_xml_to_ordered_dict(xml_text)
    flat = flatten_structure(tree)
    return flattened_to_markdown(
        flat,
        raw_text,
        include_source_block=include_source_block,
        generate_toc=generate_toc,
        fence_lang="xml",
    )
