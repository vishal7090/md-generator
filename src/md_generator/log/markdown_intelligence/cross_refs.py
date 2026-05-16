from __future__ import annotations


def inject_related_section(body: str, related_ids: list[str]) -> str:
    if not related_ids:
        return body
    lines = [body.rstrip(), "", "## Related", ""]
    for rid in related_ids[:20]:
        lines.append(f"- [{rid}]({rid})")
    lines.append("")
    return "\n".join(lines)
