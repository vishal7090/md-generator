from __future__ import annotations

import re
from pathlib import Path


def parse_project_version_and_scripts(pyproject_path: Path) -> tuple[str, dict[str, str]]:
    text = pyproject_path.read_text(encoding="utf-8")
    version = "0.0.0"
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if m:
        version = m.group(1)
    scripts: dict[str, str] = {}
    in_scripts = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if stripped.startswith("[") and in_scripts:
            break
        if not in_scripts or not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.split("#", 1)[0].strip().strip('"').strip("'")
        scripts[key] = val
    return version, scripts


def area_for_script_target(target: str) -> str | None:
    """Map 'md_generator.pdf.converter:main' -> 'pdf'; 'md_generator.media.audio.api.run:main' -> 'media'."""
    if not target.startswith("md_generator."):
        return None
    rest = target[len("md_generator.") :]
    return rest.split(".", 1)[0] if rest else None


def scripts_by_area(scripts: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, target in scripts.items():
        area = area_for_script_target(target)
        if area is None:
            continue
        out.setdefault(area, []).append(name)
    for k in out:
        out[k] = sorted(set(out[k]))
    return out
