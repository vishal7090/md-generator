"""Markdown writers for extracted business rules and combined entry documentation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Sequence

from md_generator.codeflow.models.ir import BusinessRule


def _md_cell(s: str, max_len: int = 400) -> str:
    t = " ".join(s.splitlines()).strip()
    t = t.replace("|", "\\|")
    if len(t) > max_len:
        return t[: max_len - 3] + "..."
    return t


def write_business_rules_markdown(path: Path, rules: Sequence[BusinessRule], *, entry_hint: str | None = None) -> None:
    lines: list[str] = ["# Business rules", ""]
    if entry_hint:
        lines.append(f"*Entry scope:* `{entry_hint}`")
        lines.append("")
    if not rules:
        lines.append("*No business rules were extracted for this slice (or optional SQL scan found nothing).*")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    by_source: dict[str, list[BusinessRule]] = defaultdict(list)
    order = ("predicate", "branch", "validation", "sql_trigger")
    for r in rules:
        by_source[r.source].append(r)

    lines.append("Summary tables group rules by origin. Confidence: **high** / *medium* / low.")
    lines.append("")

    for src in order:
        bucket = by_source.get(src)
        if not bucket:
            continue
        title = {
            "predicate": "Predicates and branch conditions (from call graph)",
            "branch": "Branch points (parser)",
            "validation": "Validation-style hints (assert, raise, decorators)",
            "sql_trigger": "SQL triggers (workspace scan)",
        }.get(src, src)
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Line | Symbol | Title | Detail | Conf. |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in sorted(bucket, key=lambda x: (x.file_path, x.line, x.title)):
            sym = _md_cell(r.symbol_id or "—", 80)
            lines.append(
                f"| {r.line} | `{sym}` | {_md_cell(r.title, 120)} | {_md_cell(r.detail, 200)} | {r.confidence} |",
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_combined_entry_markdown(entry_path: Path, rules_path: Path, combined_path: Path) -> None:
    """Concatenate main entry doc and business rules for a single exportable file."""
    entry_body = entry_path.read_text(encoding="utf-8").rstrip()
    rules_body = rules_path.read_text(encoding="utf-8").strip()
    combined = entry_body + "\n\n---\n\n" + rules_body + "\n"
    combined_path.write_text(combined, encoding="utf-8")
