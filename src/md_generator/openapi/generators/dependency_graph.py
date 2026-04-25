from __future__ import annotations

from md_generator.openapi.models.domain import EndpointDoc


def build_dependency_edges(endpoints: tuple[EndpointDoc, ...]) -> list[tuple[str, str]]:
    """Directed edges A->B: B consumes schemas produced by A, or explicit OpenAPI links."""
    by_oid = {ep.operation_id: ep for ep in endpoints}
    edges: set[tuple[str, str]] = set()
    for a in sorted(endpoints, key=lambda e: e.operation_id):
        for oid in sorted(a.link_operation_ids):
            if oid in by_oid and oid != a.operation_id:
                edges.add((a.operation_id, oid))
    for a in sorted(endpoints, key=lambda e: e.operation_id):
        for b in sorted(endpoints, key=lambda e: e.operation_id):
            if a.operation_id == b.operation_id:
                continue
            if a.response_schema_refs & b.request_schema_refs:
                edges.add((a.operation_id, b.operation_id))
    return sorted(edges)


def _node_ids(endpoints: tuple[EndpointDoc, ...]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for i, ep in enumerate(sorted(endpoints, key=lambda e: e.operation_id)):
        mapping[ep.operation_id] = f"N{i}"
    return mapping


def render_dependency_mermaid(endpoints: tuple[EndpointDoc, ...]) -> str:
    ids = _node_ids(endpoints)
    lines = ["graph LR"]
    for ep in sorted(endpoints, key=lambda e: e.operation_id):
        nid = ids[ep.operation_id]
        label = f"{ep.method.value.upper()} {ep.path}"
        safe = label.replace('"', "'").replace("]", ")")
        lines.append(f'    {nid}["{safe}"]')
    for a, b in build_dependency_edges(endpoints):
        lines.append(f"    {ids[a]} --> {ids[b]}")
    return "\n".join(lines) + "\n"


def render_dependency_dot(endpoints: tuple[EndpointDoc, ...]) -> str:
    ids = _node_ids(endpoints)
    lines = ["digraph ApiDependency {", "  rankdir=LR;"]
    for ep in sorted(endpoints, key=lambda e: e.operation_id):
        nid = ids[ep.operation_id]
        label = f"{ep.method.value.upper()} {ep.path}"
        safe = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  {nid} [label="{safe}"];')
    for a, b in build_dependency_edges(endpoints):
        lines.append(f"  {ids[a]} -> {ids[b]};")
    lines.append("}")
    return "\n".join(lines) + "\n"
