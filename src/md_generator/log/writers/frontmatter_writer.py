from __future__ import annotations

from typing import Any


def _yaml_escape(value: str) -> str:
    if any(c in value for c in ':\n#"\'{}[]'):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def render_frontmatter(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""
    lines = ["---"]
    for key in sorted(metadata.keys()):
        val = metadata[key]
        if val is None:
            continue
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        elif isinstance(val, list):
            lines.append(f"{key}:")
            for item in sorted(str(x) for x in val):
                lines.append(f"  - {_yaml_escape(item)}")
        elif isinstance(val, dict):
            lines.append(f"{key}:")
            for sk in sorted(val.keys()):
                sv = val[sk]
                if isinstance(sv, bool):
                    lines.append(f"  {sk}: {'true' if sv else 'false'}")
                else:
                    lines.append(f"  {sk}: {_yaml_escape(str(sv))}")
        else:
            lines.append(f"{key}: {_yaml_escape(str(val))}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def wrap_with_frontmatter(body: str, metadata: dict[str, Any], *, enabled: bool) -> str:
    if not enabled or not metadata:
        return body
    return render_frontmatter(metadata) + body
