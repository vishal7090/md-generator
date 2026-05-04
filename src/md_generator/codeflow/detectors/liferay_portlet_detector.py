"""Detect Liferay / JSR-286 portlet entry methods (extends portlet base or mapping annotations)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import javalang.tree

from md_generator.codeflow.models.ir import EntryKind, EntryRecord

logger = logging.getLogger(__name__)


def _sid(key: str, cls: str | None, name: str) -> str:
    if cls:
        return f"{key}::{cls}.{name}"
    return f"{key}::{name}"


_PORTLET_BASES_DEFAULT = frozenset(
    {
        "GenericPortlet",
        "MVCPortlet",
        "LiferayPortlet",
        "BaseStrutsPortlet",
        "Portlet",
        "BasePortlet",
        "CustomPortlet",
        "BaseMVCPortlet",
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


def _effective_bases(extra: frozenset[str] | None) -> frozenset[str]:
    return _PORTLET_BASES_DEFAULT | (extra or frozenset())


def _extends_portlet_base(t: object, bases: frozenset[str]) -> bool:
    for ext in getattr(t, "extends", None) or []:
        tail = _reference_simple_name(ext)
        if tail and tail in bases:
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


_LIFECYCLE_NAME_RE = re.compile(
    r"\b(processAction|serveResource|doView|doEdit|doHelp|doConfig|render)\s*\(",
)


def _file_might_contain_portlet(text: str) -> bool:
    """Loose prefilter: avoid parsing obviously unrelated Java when possible."""
    if "Portlet" in text or "portlet" in text.lower():
        return True
    if "@ProcessAction" in text or "@RenderMapping" in text or "@ResourceMapping" in text:
        return True
    if _LIFECYCLE_NAME_RE.search(text):
        return True
    if re.search(r"\bextends\s+\w*Portlet\w*", text):
        return True
    return False


def _iter_class_declarations(cdecl: object, prefix: tuple[str, ...]) -> list[tuple[str, object]]:
    """Flatten outer and nested class declarations: (qualified_name, ClassDeclaration)."""
    out: list[tuple[str, object]] = []
    name = getattr(cdecl, "name", None) or ""
    parts = prefix + (name,)
    fq = ".".join(parts)
    out.append((fq, cdecl))
    for item in getattr(cdecl, "body", None) or []:
        if isinstance(item, javalang.tree.ClassDeclaration):
            out.extend(_iter_class_declarations(item, parts))
    return out


def detect_liferay_portlet_entries(
    path: Path,
    project_root: Path,
    *,
    extra_portlet_bases: frozenset[str] | None = None,
) -> list[EntryRecord]:
    bases = _effective_bases(extra_portlet_bases)
    text = path.read_text(encoding="utf-8", errors="replace")
    if not _file_might_contain_portlet(text):
        return []
    try:
        tree = javalang.parse.parse(text)
    except Exception as e:
        logger.debug("liferay javalang parse failed %s: %s", path, e)
        return []

    try:
        key = path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        key = path.as_posix()

    lifecycle = _portlet_lifecycle_names()
    seen: set[str] = set()
    out: list[EntryRecord] = []

    for top in tree.types or []:
        if not isinstance(top, javalang.tree.ClassDeclaration):
            continue
        for fq_name, cdecl in _iter_class_declarations(top, ()):
            portlet_class = _extends_portlet_base(cdecl, bases)
            for m in getattr(cdecl, "methods", None) or []:
                name = getattr(m, "name", None)
                if not name:
                    continue
                sid = _sid(key, fq_name, name)
                anns = _annotation_names(m)
                pos = getattr(m, "position", None)
                line = int(getattr(pos, "line", 0) or 0) if pos else 0

                if anns & _MAPPING_ANNS:
                    if sid in seen:
                        continue
                    seen.add(sid)
                    hit = sorted(anns & _MAPPING_ANNS)[0]
                    out.append(
                        EntryRecord(
                            symbol_id=sid,
                            kind=EntryKind.PORTLET,
                            label=f"Liferay portlet mapping ({hit})",
                            file_path=str(path.resolve()),
                            line=line,
                        ),
                    )
                    continue

                if name in lifecycle:
                    if sid in seen:
                        continue
                    seen.add(sid)
                    reason = "lifecycle" if portlet_class else "lifecycle_heuristic"
                    out.append(
                        EntryRecord(
                            symbol_id=sid,
                            kind=EntryKind.PORTLET,
                            label=f"Liferay portlet {reason} ({name})",
                            file_path=str(path.resolve()),
                            line=line,
                        ),
                    )

    if out:
        logger.debug("liferay: %d portlet entries from %s", len(out), path)
    return out
