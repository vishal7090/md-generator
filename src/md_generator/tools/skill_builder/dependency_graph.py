from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path


def _top_level_packages(md_root: Path) -> frozenset[str]:
    out: set[str] = set()
    if not md_root.is_dir():
        return frozenset()
    for child in md_root.iterdir():
        if child.name.startswith("_") or child.name == "__pycache__":
            continue
        if child.is_dir() and (child / "__init__.py").is_file():
            out.add(child.name)
    return frozenset(out)


def _package_for_source_file(md_root: Path, path: Path) -> str | None:
    try:
        rel = path.relative_to(md_root)
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    if len(parts) == 1:
        # e.g. engine_cli.py
        return "__root__"
    return parts[0]


def _targets_from_import(node: ast.AST, top_levels: frozenset[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            name = alias.name
            if name == "md_generator" or name.startswith("md_generator."):
                rest = name[len("md_generator.") :] if name.startswith("md_generator.") else ""
                if not rest:
                    continue
                first = rest.split(".", 1)[0]
                if first in top_levels:
                    found.add(first)
    elif isinstance(node, ast.ImportFrom):
        if node.level != 0:
            return found
        mod = node.module
        if not mod:
            return found
        if mod == "md_generator" or mod.startswith("md_generator."):
            rest = mod[len("md_generator.") :] if mod.startswith("md_generator.") else ""
            if not rest:
                return found
            first = rest.split(".", 1)[0]
            if first in top_levels:
                found.add(first)
    return found


def iter_md_generator_py_files(md_root: Path) -> list[Path]:
    return sorted(p for p in md_root.rglob("*.py") if "__pycache__" not in p.parts)


def build_dependency_graph(md_root: Path) -> dict:
    """Return a JSON-serializable graph: nodes (packages + __root__), weighted edges."""
    top = _top_level_packages(md_root)
    nodes_set: set[str] = set(top) | {"__root__"}
    edge_counts: Counter[tuple[str, str]] = Counter()

    for path in iter_md_generator_py_files(md_root):
        src_pkg = _package_for_source_file(md_root, path)
        if src_pkg is None or (src_pkg != "__root__" and src_pkg not in top):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for tgt in _targets_from_import(node, top):
                    if tgt == src_pkg:
                        continue
                    edge_counts[(src_pkg, tgt)] += 1

    nodes = sorted(nodes_set)
    edges = [
        {"source": s, "target": t, "weight": w}
        for (s, t), w in sorted(edge_counts.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    return {
        "schemaVersion": "1.0.0",
        "packageRoot": "md_generator",
        "sourceScanRoot": str(md_root.as_posix()),
        "nodes": nodes,
        "edges": edges,
    }


def write_dependency_graph(md_root: Path, out_path: Path) -> None:
    data = build_dependency_graph(md_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
