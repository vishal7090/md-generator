from __future__ import annotations

from pathlib import Path

from md_generator.log.aggregation.aggregators import level_counts, top_messages
from md_generator.log.aggregation.timeline import hourly_timeline
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_levels_md(root: Path, records: list[LogRecord]) -> None:
    counts = level_counts(records)
    lines = ["# Log levels", "", "| Level | Count |", "| --- | ---:|"]
    for k in sorted(counts.keys(), key=lambda x: (-counts[x], x)):
        lines.append(f"| {k} | {counts[k]} |")
    write_text(root / "summary" / "levels.md", "\n".join(lines) + "\n")


def write_timeline_md(root: Path, records: list[LogRecord], timeline_mode: str) -> None:
    lines = ["# Timeline", ""]
    if timeline_mode == "none" or not records:
        lines.append("_No timeline (disabled or empty)._")
        write_text(root / "summary" / "timeline.md", "\n".join(lines) + "\n")
        return
    df = hourly_timeline(records)
    if df.empty:
        lines.append("_No parseable timestamps._")
    else:
        lines.extend(["| Bucket (UTC) | Count |", "| --- | ---:|"])
        for _, row in df.iterrows():
            lines.append(f"| {row['time_bucket']} | {int(row['count'])} |")
    write_text(root / "summary" / "timeline.md", "\n".join(lines) + "\n")


def write_top_errors_md(root: Path, records: list[LogRecord]) -> None:
    err = [r for r in records if r.level.upper() in {"ERROR", "FATAL"}]
    top = top_messages(err, n=30) if err else []
    lines = ["# Top errors", "", f"Total error/fatal records: **{len(err)}**", ""]
    if not top:
        lines.append("_No errors._")
    else:
        lines.extend(["| Count | Message (truncated) |", "| ---:| --- |"])
        for msg, c in top:
            safe = msg.replace("|", "\\|").replace("\n", " ")[:400]
            lines.append(f"| {c} | {safe} |")
    write_text(root / "summary" / "top_errors.md", "\n".join(lines) + "\n")
