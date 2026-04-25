from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from md_generator.openapi.generators.dependency_graph import render_dependency_dot, render_dependency_mermaid
from md_generator.openapi.models.domain import ApiSpecMeta, EndpointDoc, SecuritySchemeDoc


def _slug_endpoint(ep: EndpointDoc) -> str:
    seg = ep.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    if not seg:
        seg = "root"
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in seg)
    return f"{ep.method.value}__{safe}"


def _json_block(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def _md_to_simple_html(md_text: str, title: str) -> str:
    body = html.escape(md_text, quote=True)
    t = html.escape(title, quote=True)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        f"<title>{t}</title></head><body><pre>{body}</pre></body></html>\n"
    )


def _format_security_scheme(s: SecuritySchemeDoc) -> str:
    parts = [f"- **{s.key}** (`{s.type}`)"]
    if s.scheme:
        parts.append(f"  - scheme: `{s.scheme}`")
    if s.bearer_format:
        parts.append(f"  - bearerFormat: `{s.bearer_format}`")
    if s.in_:
        parts.append(f"  - in: `{s.in_}`")
    if s.name:
        parts.append(f"  - name: `{s.name}`")
    if s.flows_summary:
        parts.append(f"  - flows: `{s.flows_summary}`")
    parts.append(f"  - inferred: `{s.auth_kind.value}`")
    return "\n".join(parts)


def format_endpoint_markdown(ep: EndpointDoc, meta: ApiSpecMeta) -> str:
    lines: list[str] = []
    lines.append(f"# {ep.method.value.upper()} `{ep.path}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **operationId**: `{ep.operation_id}`")
    if ep.summary:
        lines.append(f"- **summary**: {ep.summary}")
    if ep.description:
        lines.append(f"- **description**: {ep.description}")
    if ep.tags:
        lines.append(f"- **tags**: {', '.join(f'`{t}`' for t in ep.tags)}")
    lines.append(f"- **CRUD intent (rule-based)**: `{ep.crud_intent}`")
    lines.append("")
    lines.append("## Security")
    lines.append("")
    if not ep.security:
        lines.append("_No operation-level security; inherits global or none._")
    else:
        for block in ep.security:
            lines.append(f"- scopes: `{', '.join(block)}`")
    lines.append("")
    lines.append("### Inferred auth types")
    lines.append("")
    for k in ep.auth_kinds:
        lines.append(f"- `{k.value}`")
    lines.append("")
    lines.append("## Parameters")
    lines.append("")
    if not ep.parameters:
        lines.append("_None._")
    else:
        for p in ep.parameters:
            lines.append(f"### `{p.name}` (`{p.in_}`)")
            lines.append("")
            lines.append(f"- **required**: `{str(p.required).lower()}`")
            if p.description:
                lines.append(f"- **description**: {p.description}")
            lines.append("")
            lines.append("```json")
            lines.append(_json_block(p.schema))
            lines.append("```")
            lines.append("")
    lines.append("")
    lines.append("## Request contract")
    lines.append("")
    if ep.request_body_media_types:
        lines.append(f"- **content types**: {', '.join(f'`{m}`' for m in ep.request_body_media_types)}")
    if ep.request_schema:
        lines.append("")
        lines.append("```json")
        lines.append(_json_block(ep.request_schema))
        lines.append("```")
    else:
        lines.append("_No request body._")
    lines.append("")
    lines.append("## Response contracts")
    lines.append("")
    for r in ep.responses:
        lines.append(f"### `{r.status}`")
        lines.append("")
        if r.description:
            lines.append(r.description)
            lines.append("")
        if r.content_media_types:
            lines.append(f"- **content types**: {', '.join(f'`{m}`' for m in r.content_media_types)}")
        if r.schema:
            lines.append("")
            lines.append("```json")
            lines.append(_json_block(r.schema))
            lines.append("```")
        lines.append("")
    lines.append("## Test cases (rule-based)")
    lines.append("")
    for tc in ep.test_cases:
        lines.append(f"### {tc.name}")
        lines.append("")
        lines.append(tc.description)
        lines.append("")
        lines.append("```json")
        lines.append(_json_block(tc.body))
        lines.append("```")
        lines.append("")
    lines.append("## Sequence (Mermaid)")
    lines.append("")
    lines.append("```mermaid")
    lines.append(ep.sequence_mermaid.rstrip("\n"))
    lines.append("```")
    lines.append("")
    lines.append(f"_Generated from `{meta.title}` v{meta.version} (`{meta.openapi_version}`)._")
    lines.append("")
    return "\n".join(lines)


def format_schema_markdown(name: str, schema: dict[str, Any]) -> str:
    lines = [
        f"# Schema `{name}`",
        "",
        "```json",
        _json_block(schema),
        "```",
        "",
    ]
    return "\n".join(lines)


def format_readme(meta: ApiSpecMeta) -> str:
    lines = [
        f"# {meta.title}",
        "",
        f"- **OpenAPI**: `{meta.openapi_version}`",
        f"- **Version**: `{meta.version}`",
        "",
        "## Servers",
        "",
    ]
    if meta.servers:
        for s in meta.servers:
            lines.append(f"- `{s}`")
    else:
        lines.append("_None declared._")
    lines.extend(["", "## Security schemes", ""])
    if not meta.security_schemes:
        lines.append("_None._")
    else:
        for k in sorted(meta.security_schemes.keys()):
            lines.append(_format_security_scheme(meta.security_schemes[k]))
            lines.append("")
    lines.extend(["", "## Endpoints", ""])
    for ep in sorted(meta.endpoints, key=lambda e: (e.path, e.method.value, e.operation_id)):
        slug = _slug_endpoint(ep)
        lines.append(f"- [{ep.method.value.upper()} {ep.path}](endpoints/{slug}.md) — `{ep.operation_id}`")
    lines.append("")
    lines.append("## Diagrams")
    lines.append("")
    lines.append("- [API dependency (Mermaid)](graphs/api_dependency.mmd)")
    lines.append("- [API dependency (DOT)](graphs/api_dependency.dot)")
    lines.append("")
    lines.append("```mermaid")
    lines.append(render_dependency_mermaid(meta.endpoints).rstrip("\n"))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_api_markdown_tree(
    meta: ApiSpecMeta,
    out: Path,
    *,
    formats: frozenset[str],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "endpoints").mkdir(parents=True, exist_ok=True)
    (out / "schemas").mkdir(parents=True, exist_ok=True)
    (out / "diagrams" / "sequence").mkdir(parents=True, exist_ok=True)
    (out / "graphs").mkdir(parents=True, exist_ok=True)

    readme = format_readme(meta)
    (out / "README.md").write_text(readme, encoding="utf-8")
    if "html" in formats:
        (out / "README.html").write_text(_md_to_simple_html(readme, meta.title), encoding="utf-8")

    summary = {
        "title": meta.title,
        "version": meta.version,
        "openapi": meta.openapi_version,
        "servers": list(meta.servers),
        "endpoints": [
            {
                "operationId": ep.operation_id,
                "method": ep.method.value,
                "path": ep.path,
                "file": f"endpoints/{_slug_endpoint(ep)}.md",
            }
            for ep in sorted(meta.endpoints, key=lambda e: (e.path, e.method.value, e.operation_id))
        ],
    }
    (out / "api_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    for ep in sorted(meta.endpoints, key=lambda e: (e.path, e.method.value, e.operation_id)):
        slug = _slug_endpoint(ep)
        md = format_endpoint_markdown(ep, meta)
        (out / "endpoints" / f"{slug}.md").write_text(md, encoding="utf-8")
        if "html" in formats:
            (out / "endpoints" / f"{slug}.html").write_text(_md_to_simple_html(md, f"{ep.method.value} {ep.path}"), encoding="utf-8")
        if "mermaid" in formats:
            seq_path = out / "diagrams" / "sequence" / f"{slug}.mmd"
            seq_path.write_text(ep.sequence_mermaid, encoding="utf-8")

    dep_mmd = render_dependency_mermaid(meta.endpoints)
    dep_dot = render_dependency_dot(meta.endpoints)
    (out / "graphs" / "api_dependency.mmd").write_text(dep_mmd, encoding="utf-8")
    (out / "graphs" / "api_dependency.dot").write_text(dep_dot, encoding="utf-8")


def write_schema_files(out: Path, schemas: dict[str, dict[str, Any]], *, formats: frozenset[str]) -> None:
    for name in sorted(schemas.keys()):
        sch = schemas[name]
        if not isinstance(sch, dict):
            continue
        md = format_schema_markdown(name, sch)
        (out / "schemas" / f"{name}.md").write_text(md, encoding="utf-8")
        if "html" in formats:
            (out / "schemas" / f"{name}.html").write_text(_md_to_simple_html(md, f"Schema {name}"), encoding="utf-8")
