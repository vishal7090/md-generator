from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

from tools.skillgen.dependency_graph import build_dependency_graph, write_dependency_graph
from tools.skillgen.pyproject_util import parse_project_version_and_scripts, scripts_by_area
from tools.skillgen.routing import AREA_SKILL_IDS, build_routing_block

# Human-readable titles for area skills
_AREA_TITLES: dict[str, str] = {
    "archive": "ZIP archive → Markdown",
    "codeflow": "Code → architecture Markdown (codeflow)",
    "db": "Database metadata → Markdown",
    "graph": "Graph (Neo4j / NetworkX) → Markdown",
    "image": "Image OCR → Markdown",
    "media": "Audio, video, YouTube → Markdown",
    "openapi": "OpenAPI → Markdown / docs bundle",
    "pdf": "PDF → Markdown",
    "playwright": "Playwright URL → Markdown",
    "ppt": "PowerPoint (.pptx) → Markdown",
    "text": "Text / JSON / XML → Markdown",
    "url": "URL (HTML) → Markdown",
    "word": "Word (.docx) → Markdown",
    "xlsx": "Excel / CSV → Markdown",
}

_EXTRA_BY_AREA: dict[str, str] = {
    "archive": "archive",
    "codeflow": "codeflow",
    "db": "db",
    "graph": "graph",
    "image": "image",
    "media": "audio,video,youtube",
    "openapi": "openapi",
    "pdf": "pdf",
    "playwright": "playwright",
    "ppt": "ppt",
    "text": "text",
    "url": "url",
    "word": "word",
    "xlsx": "xlsx",
}

_SKILL_NAME = "mdengine-ai-{area}"
_DESCRIPTION_SEEDS: dict[str, str] = {
    "pdf": "Documents pip-installed mdengine features for PDF → Markdown: extras, CLIs, and public imports under md_generator.pdf.",
    "word": "Documents pip-installed mdengine features for Word (DOCX) → Markdown: extras, CLIs, and public imports under md_generator.word.",
    "ppt": "Documents pip-installed mdengine features for PowerPoint → Markdown: extras, CLIs, and public imports under md_generator.ppt.",
    "xlsx": "Documents pip-installed mdengine features for Excel/CSV → Markdown: extras, CLIs, and public imports under md_generator.xlsx.",
    "image": "Documents pip-installed mdengine features for Image OCR → Markdown: extras, CLIs, and public imports under md_generator.image.",
    "text": "Documents pip-installed mdengine features for Text/JSON/XML → Markdown: extras, CLIs, and public imports under md_generator.text.",
    "archive": "Documents pip-installed mdengine features for ZIP archive → Markdown: extras, CLIs, and public imports under md_generator.archive.",
    "url": "Documents pip-installed mdengine features for URL (HTML) → Markdown: extras, CLIs, and public imports under md_generator.url.",
    "playwright": "Documents pip-installed mdengine features for Playwright URL → Markdown: extras, CLIs, and public imports under md_generator.playwright.",
    "db": "Documents pip-installed mdengine features for Database → Markdown: extras, CLIs, and public imports under md_generator.db.",
    "graph": "Documents pip-installed mdengine features for Graph → Markdown: extras, CLIs, and public imports under md_generator.graph.",
    "openapi": "Documents pip-installed mdengine features for OpenAPI → Markdown: extras, CLIs, and public imports under md_generator.openapi.",
    "codeflow": "Documents pip-installed mdengine features for Codeflow (code → Markdown): extras, CLIs, and public imports under md_generator.codeflow.",
    "media": "Documents pip-installed mdengine features for media (audio/video/YouTube) → Markdown: extras, CLIs, and public imports under md_generator.media.",
}


def _list_subpackages(md_root: Path, area: str, limit: int = 20) -> list[str]:
    base = md_root / area
    if not base.is_dir():
        return []
    names: list[str] = []
    for p in sorted(base.iterdir()):
        if p.name.startswith("_") or p.name == "__pycache__":
            continue
        if p.is_dir() and (p / "__init__.py").is_file():
            names.append(p.name)
        elif p.suffix == ".py" and p.name != "__init__.py":
            names.append(p.stem)
    return names[:limit]


def _package_doc(md_root: Path, area: str) -> str:
    init_path = md_root / area / "__init__.py"
    if not init_path.is_file():
        return ""
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree)
    return " ".join(doc.split()).strip() if doc else ""


def _scan_optional_imports(md_root: Path, area: str, max_files: int = 40) -> list[str]:
    hints: list[str] = []
    base = md_root / area
    if not base.is_dir():
        return hints
    files = sorted([p for p in base.rglob("*.py") if "__pycache__" not in p.parts])[:max_files]
    for path in files:
        try:
            t = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "ImportError" in t and "try" in t:
            rel = path.relative_to(md_root)
            hints.append(f"`{rel.as_posix()}`: optional imports / ImportError handling")
            if len(hints) >= 6:
                break
    return hints


def _description_line(area: str, scripts: list[str], doc: str) -> str:
    seed = _DESCRIPTION_SEEDS.get(
        area,
        f"Documents pip-installed mdengine features for `{area}`: extras, CLIs, and public imports under `md_generator.{area}`.",
    )
    triggers = ", ".join(f"`{s}`" for s in scripts[:5])
    if len(scripts) > 5:
        triggers += ", …"
    tail = f" Use when the user mentions {triggers} or needs this capability after installing mdengine from PyPI."
    base = seed + tail
    if doc and doc not in base:
        base += f" Package summary: {doc}"
    return " ".join(base.split())


def _build_area_skill_body(
    area: str,
    scripts: list[str],
    md_root: Path,
) -> str:
    title = _AREA_TITLES.get(area, f"{area} (mdengine)")
    doc = _package_doc(md_root, area)
    subs = _list_subpackages(md_root, area)
    extras = _EXTRA_BY_AREA.get(area, area)
    optional_hints = _scan_optional_imports(md_root, area)
    primary_cli = scripts[0] if scripts else "(see pyproject.toml)"
    pip_extras = extras if "," not in extras else extras.replace(",", ", ")

    subs_block = ", ".join(f"`{s}`" for s in subs) if subs else "(flat package)"

    edge_parts = (
        [f"- {h}" for h in optional_hints]
        if optional_hints
        else ["- Install the correct **optional extra** for this area; missing deps surface at import or first CLI use."]
    )
    edge_parts.append("- Prefer **`--help`** on each CLI before guessing flags.")
    edge_lines = "\n".join(edge_parts)

    script_lines = "\n".join(f"- `{n}`" for n in scripts) if scripts else "- _(no console scripts mapped to this package in pyproject.toml)_"
    purpose = doc or (
        f"Convert and document workflows for `{area}` via the `md_generator.{area}` package after `pip install mdengine[...]`."
    )
    body = f"""# mdengine — {title}

<!-- Generated by tools/skillgen — prefer editing references/example.md or the generator. -->

## Purpose

{purpose}

## Input / output

- **Inputs:** Files, URLs, specs, or API payloads handled by this area’s CLIs (see below). Primary CLI example: `{primary_cli}`.
- **Outputs:** Markdown (and optional sidecar artifacts) per **`--help`** on each script and the upstream README.

## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[{pip_extras}]"
```

(Adjust extras to match the features you need.)

## Primary entry points (from pyproject)

{script_lines}

## Core layout (from repository scan)

- **Package:** `md_generator.{area}`
- **Notable modules / subpackages:** {subs_block}

## Edge cases (heuristic)

{edge_lines}

## Prompt templates

### Feature work

- Goal uses **`md_generator.{area}`** after `pip install "mdengine[{pip_extras}]"`.
- List the smallest CLI or public API path; cite **`--help`** for flags not duplicated here.

### Debug

- Confirm extras and entry points; reproduce with `{primary_cli} --help` then minimal repro command.
- If imports fail, inspect optional-dependency patterns noted above.

### Refactor

- Preserve `pyproject.toml` script targets under `md_generator.{area}` unless releasing a breaking change.
- Keep Markdown output contracts stable for integrators.

## APIs / MCP

See [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[api,mcp]`** plus this area’s extras.

## See also

- [Global architecture skill](../global-skill.md)
- [Consumer global skill](../mdengine-ai-global/SKILL.md)
- [CLI reference](../mdengine-reference/SKILL.md)
"""
    return body.rstrip() + "\n"


def _yaml_frontmatter(name: str, description: str, version: str) -> str:
    safe = " ".join(description.split())
    safe = safe.replace("\\", "\\\\").replace('"', '\\"')
    return f'---\nname: {name}\ndescription: "{safe}"\nversion: {version}\n---\n'


def _areas_from_filesystem(md_root: Path) -> list[str]:
    out: list[str] = []
    for child in sorted(md_root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if (child / "__init__.py").is_file():
            out.append(child.name)
    return out


def _git_changed_areas(repo_root: Path, ref: str) -> set[str] | None:
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", ref, "--", "src/md_generator"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if r.returncode != 0:
        return None
    areas: set[str] = set()
    for line in r.stdout.splitlines():
        line = line.strip().replace("\\", "/")
        if not line.startswith("src/md_generator/"):
            continue
        parts = line.split("/")
        if len(parts) >= 3:
            areas.add(parts[2])
    return areas


def build_global_skill_md(version: str, graph: dict, areas: list[str]) -> str:
    nodes = [n for n in graph.get("nodes", []) if n not in ("__root__",)]
    edges = [e for e in graph.get("edges", []) if e.get("source") != "__root__" or e.get("target") in nodes]
    edge_sample = edges[:60]
    mermaid_lines = ["flowchart LR"]
    for n in nodes[:22]:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", n)
        mermaid_lines.append(f'  {safe}["{n}"]')
    for e in edge_sample:
        s, t = e.get("source"), e.get("target")
        if s in ("__root__",) or t in ("__root__",):
            continue
        if s not in nodes or t not in nodes:
            continue
        ss = re.sub(r"[^a-zA-Z0-9_]", "_", s)
        tt = re.sub(r"[^a-zA-Z0-9_]", "_", t)
        mermaid_lines.append(f"  {ss} --> {tt}")
    mermaid = "\n".join(mermaid_lines)

    area_list = ", ".join(f"`{a}`" for a in areas)
    desc = (
        "Code-derived system view of mdengine: package boundaries, import relationships between "
        "md_generator top-level modules, and how CLIs/APIs/MCP routes relate. Use for cross-area "
        "questions; defer per-area details to mdengine-ai-<area> skills."
    )
    header = _yaml_frontmatter("mdengine-global-architecture", desc, version)
    body = f"""# mdengine — global architecture (generated)

<!-- Generated by tools/skillgen from src/md_generator + dependency graph. -->

## Workflow (high level)

1. User picks **optional extras** and installs `mdengine` from PyPI (`import md_generator`).
2. **Console scripts** (`md-*`, `mdengine …`) invoke package-specific CLIs under `md_generator.<area>`.
3. Some areas expose **FastAPI** (`*-api`) and **MCP** (`*-mcp`) entry points documented in `mdengine-reference`.
4. Outputs are typically **Markdown** plus optional assets; job-style APIs may use async patterns described in reference docs.

## Module set

Top-level installable feature packages discovered on disk: {area_list}.

## Data flow

- **In:** Files, URLs, DB connections, graphs, media binaries, OpenAPI specs, source trees (codeflow).
- **Out:** Markdown strings/files; optional JSON/HTML bundles for codeflow/OpenAPI as documented upstream.

## Cross-package import graph (excerpt)

The full graph lives in `ai/dependency-graph.json` (edges include weights). Simplified view:

```mermaid
{mermaid}
```

## Where to go next

- Per-area behavior: `ai/skills/mdengine-ai-<area>/SKILL.md`
- Consumer install / extras table: `ai/skills/mdengine-ai-global/SKILL.md`
- CLI / HTTP / MCP tables: `ai/skills/mdengine-reference/`
"""
    return header + body.rstrip() + "\n"


def build_global_consumer_skill_md(version: str) -> str:
    desc = (
        "Teaches use of the mdengine PyPI package after pip install: optional extras, "
        "console scripts, FastAPI and MCP entry points, and imports under md_generator. "
        "For architecture between packages, see ../global-skill.md."
    )
    body = textwrap.dedent(
        """
        # mdengine — global skill (pip-installed library)

        <!-- Generated by tools/skillgen — architecture: ../global-skill.md -->

        ## Architecture (system)

        See **[global-skill.md](../global-skill.md)** for import graph, pipeline, and cross-area flow (generated from source).

        ## Examples

        Concrete commands: [references/example.md](references/example.md).

        ## Install

        ```bash
        pip install "mdengine[pdf,word]"   # pick extras you need; see table below
        python -c "import md_generator; print('ok')"
        ```

        Python **3.10+**. Distribution name on PyPI: **`mdengine`**. Import package: **`md_generator`**.

        ### Optional extras (summary)

        | Extra | Enables |
        |-------|---------|
        | `pdf` | PDF → Markdown (`md-pdf`) |
        | `word` | DOCX → Markdown (`md-word`) |
        | `ppt` | PPTX → Markdown (`md-ppt`) |
        | `xlsx` | Excel/CSV → Markdown (`md-xlsx`) |
        | `image` / `image-ocr` | Raster OCR (`md-image`) |
        | `text` | TXT / JSON / XML (`md-text`) |
        | `archive` | ZIP extraction pipeline (`md-zip`) |
        | `url` / `url-full` | URL → Markdown (`md-url`; `url-full` adds post-convert for downloads) |
        | `audio` / `video` / `youtube` | Media transcription / YouTube (`md-audio`, `md-video`, `md-youtube` + APIs/MCP) |
        | `playwright` | Headless browser capture (`md-playwright` + API/MCP); run `playwright install chromium` |
        | `db` | DB metadata → Markdown (`md-db`, `md-db-api`, `md-db-mcp`) |
        | `graph` | Neo4j / NetworkX → Markdown (`md-graph`, …) |
        | `openapi` | OpenAPI → docs (`md-openapi`, …) |
        | `codeflow` | Code → architecture Markdown (`md-codeflow`, …); optional `codeflow-treesitter`, `codeflow-clang` |
        | `api` / `mcp` | Shared HTTP / MCP stacks where those entry points exist |
        | `all` | Large superset — avoid unless truly needed |

        Full matrix and behavior: upstream **README** on PyPI / repository.

        ## Command-line tools

        Every installed command exposes **`--help`**. Common pattern:

        ```bash
        md-pdf input.pdf output.md
        md-url https://example.com/page ./out --artifact-layout
        ```

        Aggregated **`mdengine`** CLI routes subcommands (e.g. `mdengine db-to-md …`, `mdengine graph-to-md …`, `mdengine openapi-to-md generate …`). Prefer **`md-*`** aliases when documented for your scenario.

        See [CLI reference](../mdengine-reference/SKILL.md) for CLI ↔ extra mapping. That skill also ships **[entrypoints.md](../mdengine-reference/references/entrypoints.md)** and **[http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md)**.

        ## HTTP APIs and MCP

        Many areas ship **FastAPI** apps (`*-api` scripts) and **MCP** servers (`*-mcp`). Default ports and routes vary by area — check **`--help`** on the installed script or upstream README.

        ## Area-specific skills

        For deep behavior (flags, APIs, ports), open the matching **sibling folder**, e.g. [PDF](../mdengine-ai-pdf/SKILL.md), [DB](../mdengine-ai-db/SKILL.md), … (`skills/mdengine-ai-<area>/SKILL.md`).

        ## Contributors (optional)

        If you maintain **mdengine** from a git clone, editable install and tests live in the upstream repository — they are **out of scope** for consumer-focused skills. Do not treat `src/...` paths as requirements for end users.

        ## Additional resources

        - [CLI reference](../mdengine-reference/SKILL.md)
        """
    ).strip()
    return _yaml_frontmatter("mdengine-ai-global", desc, version) + body + "\n"


def write_module_mirror(ai_root: Path, area: str, skill_md: str) -> None:
    mod_dir = ai_root / "skills" / "modules"
    mod_dir.mkdir(parents=True, exist_ok=True)
    # Strip YAML frontmatter for flat module mirror
    parts = skill_md.split("---", 2)
    body = skill_md if len(parts) < 3 else parts[2].lstrip("\n")
    (mod_dir / f"{area}.md").write_text(f"# Module: {area}\n\n{body}", encoding="utf-8")


def run_generate(repo_root: Path, since_ref: str | None = None) -> None:
    pyproject = repo_root / "pyproject.toml"
    md_root = repo_root / "src" / "md_generator"
    ai_root = repo_root / "ai"
    version, scripts_map = parse_project_version_and_scripts(pyproject)
    by_area = scripts_by_area(scripts_map)
    areas_fs = _areas_from_filesystem(md_root)
    if since_ref:
        changed = _git_changed_areas(repo_root, since_ref)
        if changed is None:
            raise SystemExit("git diff failed; need a git repo and valid ref for --since")
        areas_to_build = [a for a in areas_fs if a in changed]
        if not areas_to_build:
            areas_to_build = []
    else:
        areas_to_build = list(areas_fs)

    write_dependency_graph(md_root, ai_root / "dependency-graph.json")
    graph = build_dependency_graph(md_root)

    global_md = build_global_skill_md(version, graph, areas_fs)
    (ai_root / "skills" / "global-skill.md").write_text(global_md + "\n", encoding="utf-8")

    # Registry: bundleVersion + routing refresh
    reg_path = ai_root / "registry.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    reg["schemaVersion"] = "1.1.0"
    reg["bundleVersion"] = version
    reg["routing"] = build_routing_block()
    reg.setdefault("agents", {})["mdengine-master-agent"] = {
        "file": "agent/master-agent.md",
        "pairedSkill": "mdengine-ai-global",
    }
    reg_path.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")

    consumer_global = build_global_consumer_skill_md(version)
    (ai_root / "skills" / "mdengine-ai-global" / "SKILL.md").write_text(consumer_global + "\n", encoding="utf-8")

    build_set = set(areas_to_build) if since_ref else set(areas_fs)

    for area in areas_fs:
        if since_ref and area not in build_set:
            continue
        skill_id = AREA_SKILL_IDS.get(area)
        if not skill_id or not skill_id.startswith("mdengine-ai-"):
            continue
        sc = by_area.get(area, [])
        doc = _package_doc(md_root, area)
        desc = _description_line(area, sc, doc)
        body = _build_area_skill_body(area, sc, md_root)
        skill_md = _yaml_frontmatter(_SKILL_NAME.format(area=area), desc, version) + body
        out = ai_root / "skills" / skill_id / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(skill_md + "\n", encoding="utf-8")
        write_module_mirror(ai_root, area, skill_md)

    _sync_sdk_data_bundle(repo_root, ai_root)


def _sync_sdk_data_bundle(repo_root: Path, ai_root: Path) -> None:
    """Copy distributable `ai/` artifacts into tools.mdengine_skill package data."""
    pkg_root = repo_root / "tools" / "mdengine_skill"
    pkg_data = pkg_root / "data"
    if not pkg_root.is_dir():
        return
    pkg_data.mkdir(parents=True, exist_ok=True)
    for name in ("registry.json", "dependency-graph.json", "skills"):
        src = ai_root / name
        dst = pkg_data / name
        if not src.exists():
            continue
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
            else:
                dst.unlink(missing_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
