from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List
from xml.etree.ElementTree import Element


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _title_tag(tag: str) -> str:
    return _local_tag(tag).replace("_", " ").replace("-", " ").title()


def _slug(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"[\s_]+", "-", t)
    return t or "section"


def _attrs_lines(el: Element, out: List[str]) -> None:
    for k, v in el.attrib.items():
        name = _local_tag(k)
        out.append(f"- **{name}:** {v}")


def _direct_text(el: Element) -> str:
    parts: list[str] = []
    if el.text and el.text.strip():
        parts.append(el.text.strip())
    return " ".join(parts)


def _uniform_children(children: list[Element]) -> bool:
    if len(children) < 2:
        return False
    tags = {_local_tag(c.tag) for c in children}
    if len(tags) != 1:
        return False
    return all(len(list(c)) == len(list(children[0])) for c in children)


def _child_signature(c: Element) -> tuple[str, ...]:
    return tuple(sorted(_local_tag(ch.tag) for ch in c))


def _table_from_siblings(children: list[Element], out: List[str]) -> None:
    rows: list[dict[str, str]] = []
    col_keys: set[str] = set()
    for ch in children:
        row: dict[str, str] = {}
        for sub in ch:
            lk = _local_tag(sub.tag)
            col_keys.add(lk)
            t = _direct_text(sub)
            if not t and len(list(sub)) == 0:
                t = ""
            elif not t:
                t = ET.tostring(sub, encoding="unicode", method="text").strip()
            row[lk] = t
        rows.append(row)
    keys = sorted(col_keys)
    if not keys:
        return
    out.append("")
    out.append("| " + " | ".join(keys) + " |")
    out.append("| " + " | ".join("---" for _ in keys) + " |")
    for row in rows:
        cells = [row.get(k, "").replace("|", "\\|") for k in keys]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")


def _emit_element(el: Element, level: int, out: List[str], toc: List[tuple[str, str]]) -> None:
    tag_title = _title_tag(el.tag)
    hp = "#" * max(2, min(6, level))
    out.append("")
    out.append(f"{hp} {tag_title}")
    toc.append((tag_title, _slug(tag_title)))
    _attrs_lines(el, out)
    text = _direct_text(el)
    if text:
        out.append("")
        out.append(text)
    children = list(el)
    if not children:
        return
    if _uniform_children(children) and all(len(list(c)) > 0 for c in children):
        sig0 = _child_signature(children[0])
        if all(_child_signature(c) == sig0 for c in children):
            _table_from_siblings(children, out)
            return
    for ch in children:
        _emit_element(ch, level + 1, out, toc)


def xml_to_markdown(root: Element, raw_text: str, *, include_source_block: bool, generate_toc: bool) -> str:
    out: List[str] = []
    toc: List[tuple[str, str]] = []
    _emit_element(root, 2, out, toc)
    body = "\n".join(out)
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")

    prefix = ""
    if generate_toc and toc:
        lines = ["## Table of contents", ""]
        for title, slug in toc:
            lines.append(f"- [{title}](#{slug})")
        lines.append("")
        prefix = "\n".join(lines)

    chunks: List[str] = []
    if prefix.strip():
        chunks.append(prefix.rstrip())
    if body.strip():
        chunks.append(body.strip())
    if include_source_block:
        chunks.append("```xml")
        chunks.append(raw_text.rstrip())
        chunks.append("```")
    return "\n\n".join(chunks).strip() + "\n"
