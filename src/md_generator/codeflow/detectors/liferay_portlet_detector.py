"""Detect Liferay / JSR-286 portlet entry methods (extends portlet base or mapping annotations)."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.models.ir import EntryKind, EntryRecord


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


_PORTLET_BASES = frozenset(
    {
        "GenericPortlet",
        "MVCPortlet",
        "LiferayPortlet",
        "BaseStrutsPortlet",
        "Portlet",
    },
)

_MAPPING_ANNS = frozenset(
    {
        "ProcessAction",
        "RenderMapping",
        "ResourceMapping",
        "ActionMapping",
        "EventMapping",
        "ServeResourceMapping",
    },
)


def _reference_simple_name(type_obj: object) -> str | None:
    """Last segment of a chained ``ReferenceType`` (e.g. ``javax.portlet.GenericPortlet`` -> ``GenericPortlet``)."""
    cur: object | None = type_obj
    last: str | None = None
    while cur is not None:
        n = getattr(cur, "name", None)
        if n:
            last = str(n)
        cur = getattr(cur, "sub_type", None)
    return last


def _extends_portlet_base(t: object) -> bool:
    for ext in getattr(t, "extends", None) or []:
        tail = _reference_simple_name(ext)
        if tail and tail in _PORTLET_BASES:
            return True
    return False


def _annotation_names(m: object) -> set[str]:
    out: set[str] = set()
    for ann in getattr(m, "annotations", None) or []:
        n = getattr(ann, "name", None) or str(ann)
        out.add(str(n).split(".")[-1])
    return out


def _portlet_lifecycle_names() -> frozenset[str]:
    return frozenset(
        {
            "processAction",
            "serveResource",
            "doView",
            "doEdit",
            "doHelp",
            "doConfig",
            "render",
        },
    )


def detect_liferay_portlet_entries(path: Path, project_root: Path) -> list[EntryRecord]:
    import javalang

    text = path.read_text(encoding="utf-8", errors="replace")
    if "Portlet" not in text and "ProcessAction" not in text and "MVCPortlet" not in text and "GenericPortlet" not in text:
        return []
    try:
        tree = javalang.parse.parse(text)
    except Exception:
        return []

    try:
        key = path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        key = path.as_posix()

    out: list[EntryRecord] = []
    for t in tree.types or []:
        cls_name = getattr(t, "name", None)
        if not cls_name:
            continue
        portlet_class = _extends_portlet_base(t)
        for m in getattr(t, "methods", None) or []:
            name = getattr(m, "name", None)
            if not name:
                continue
            anns = _annotation_names(m)
            if anns & _MAPPING_ANNS:
                pos = getattr(m, "position", None)
                line = int(getattr(pos, "line", 0) or 0) if pos else 0
                hit = sorted(anns & _MAPPING_ANNS)[0]
                out.append(
                    EntryRecord(
                        symbol_id=_sid(key, cls_name, name),
                        kind=EntryKind.PORTLET,
                        label=f"Liferay portlet mapping ({hit})",
                        file_path=str(path.resolve()),
                        line=line,
                    ),
                )
                continue
            if portlet_class and name in _portlet_lifecycle_names():
                pos = getattr(m, "position", None)
                line = int(getattr(pos, "line", 0) or 0) if pos else 0
                out.append(
                    EntryRecord(
                        symbol_id=_sid(key, cls_name, name),
                        kind=EntryKind.PORTLET,
                        label=f"Liferay portlet lifecycle ({name})",
                        file_path=str(path.resolve()),
                        line=line,
                    ),
                )
    return out
