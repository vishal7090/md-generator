from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def group_incidents(records: list[LogRecord]) -> dict[str, list[LogRecord]]:
    by_fp: dict[str, list[LogRecord]] = defaultdict(list)
    for r in records:
        key = r.fingerprint or r.message[:200]
        by_fp[key].append(r)
    return {k: v for k, v in by_fp.items() if len(v) >= 2}


def write_incidents(root: Path, records: list[LogRecord]) -> None:
    groups = group_incidents(records)
    sorted_groups = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for i, (_fp, rs) in enumerate(sorted_groups[:200], start=1):
        rs_sorted = sorted(rs, key=lambda x: (x.timestamp or x.line_number))
        first = rs_sorted[0]
        last = rs_sorted[-1]
        title = first.message.replace("\n", " ")[:80]
        lines = [
            f"# Incident {i:03d}",
            "",
            f"**Occurrences:** {len(rs)}",
            f"**First seen:** {first.timestamp or 'n/a'} (line {first.line_number}, `{first.source_file.name}`)",
            f"**Last seen:** {last.timestamp or 'n/a'}",
            "",
            "## Representative messages",
            "",
        ]
        for r in rs_sorted[:8]:
            m = r.message.replace("\n", " ")[:500]
            lines.append(f"- `{r.level}` — {m}")
        if len(rs_sorted) > 8:
            lines.append(f"- … _{len(rs_sorted) - 8} more_")
        lines.append("")
        write_text(root / "incidents" / f"incident_{i:03d}.md", "\n".join(lines))
