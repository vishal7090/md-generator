"""Framework-specific API entry hints (REST)."""

from __future__ import annotations

import ast
from pathlib import Path

from md_generator.codeflow.models.ir import EntryKind, EntryRecord


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


def detect_api_entries_python(path: Path, project_root: Path) -> list[EntryRecord]:
    key = path.resolve().relative_to(project_root.resolve()).as_posix()
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(path))
    out: list[EntryRecord] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            deco_names: list[str] = []
            for d in node.decorator_list:
                name = ""
                if isinstance(d, ast.Name):
                    name = d.id
                elif isinstance(d, ast.Attribute):
                    name = d.attr
                elif isinstance(d, ast.Call):
                    func = d.func
                    if isinstance(func, ast.Attribute):
                        name = func.attr
                    elif isinstance(func, ast.Name):
                        name = func.id
                deco_names.append(name.lower())
                try:
                    deco_names.append(ast.unparse(d).lower())
                except Exception:
                    pass
            blob = " ".join(deco_names)
            # FastAPI / Flask-style heuristics
            if any(
                x in blob
                for x in (
                    "router.get",
                    "router.post",
                    "router.put",
                    "router.delete",
                    "router.patch",
                    "route",
                    "get",
                    "post",
                    "put",
                    "delete",
                    "api_route",
                )
            ):
                cls = None
                for p in ast.walk(tree):
                    if isinstance(p, ast.ClassDef) and node in p.body:
                        cls = p.name
                        break
                out.append(
                    EntryRecord(
                        symbol_id=_sid(key, cls, node.name),
                        kind=EntryKind.API_REST,
                        label="Python API route (heuristic)",
                        file_path=str(path.resolve()),
                        line=node.lineno,
                    )
                )
    return out


def detect_api_entries_java(path: Path, project_root: Path) -> list[EntryRecord]:
    text = path.read_text(encoding="utf-8", errors="replace")
    key = path.resolve().relative_to(project_root.resolve()).as_posix()
    out: list[EntryRecord] = []
    if "@RestController" not in text and "@RequestMapping" not in text:
        return out
    try:
        import javalang

        tree = javalang.parse.parse(text)
    except Exception:
        return out

    for t in tree.types or []:
        cls_name = getattr(t, "name", "")
        restish = False
        for ann in getattr(t, "annotations", None) or []:
            an = getattr(ann, "name", None) or str(ann)
            if an in ("RestController", "Controller", "RequestMapping"):
                restish = True
                break
        if not restish:
            continue
        for m in getattr(t, "methods", None) or []:
            names = []
            for ann in getattr(m, "annotations", None) or []:
                names.append(str(getattr(ann, "name", ann)))
            if any(n.startswith(("GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping", "RequestMapping")) for n in names):
                sym = _sid(key, cls_name, m.name)
                out.append(
                    EntryRecord(
                        symbol_id=sym,
                        kind=EntryKind.API_REST,
                        label="Java Spring MVC mapping",
                        file_path=str(path.resolve()),
                        line=int(getattr(getattr(m, "position", None), "line", 0) or 0),
                    )
                )
    return out


def detect_api_entries(path: Path, project_root: Path) -> list[EntryRecord]:
    suf = path.suffix.lower()
    if suf == ".py":
        return detect_api_entries_python(path, project_root)
    if suf == ".java":
        return detect_api_entries_java(path, project_root)
    return []
