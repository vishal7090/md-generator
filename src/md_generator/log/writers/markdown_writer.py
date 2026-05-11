from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import ensure_dir, write_text
from md_generator.log.writers.cluster_markdown import write_cluster_files
from md_generator.log.writers.incident_writer import write_incidents
from md_generator.log.writers.summary_writer import write_levels_md, write_timeline_md, write_top_errors_md


def write_readme(root: Path, records: list[LogRecord], *, title: str = "Log export") -> None:
    lines = [
        f"# {title}",
        "",
        "## Overview",
        "",
        f"- **Total records:** {len(records)}",
        "",
        "## Artifact layout",
        "",
        "- `summary/` — aggregates and timelines",
        "- `raw/` — level-split excerpts",
        "- `incidents/` — grouped failures (when enabled)",
        "- `clusters/` — clustering output (when enabled)",
        "- `chunks/` — RAG-oriented slices (when enabled)",
        "",
        "## Navigation",
        "",
        "- [Levels](summary/levels.md)",
        "- [Timeline](summary/timeline.md)",
        "- [Top errors](summary/top_errors.md)",
        "",
    ]
    write_text(root / "README.md", "\n".join(lines))


def write_raw_by_level(root: Path, records: list[LogRecord]) -> None:
    by_lvl: dict[str, list[LogRecord]] = {}
    for r in records:
        by_lvl.setdefault(r.level.upper(), []).append(r)

    for lvl, rs in sorted(by_lvl.items()):
        lines = [f"# {lvl}", ""]
        for r in rs[:5000]:
            ts = r.timestamp.isoformat() if r.timestamp else ""
            lines.append(f"- `{ts}` {r.message[:800].replace(chr(10), ' ')}")
        if len(rs) > 5000:
            lines.append(f"\n_… truncated, {len(rs) - 5000} more records_")
        fname = f"{lvl.lower()}.md"
        write_text(root / "raw" / fname, "\n".join(lines) + "\n")


def render_all(
    root: Path,
    records: list[LogRecord],
    cfg: LogRunConfig,
    *,
    cluster_labels: list[int] | None = None,
) -> None:
    ensure_dir(root)
    ensure_dir(root / "summary")
    ensure_dir(root / "raw")
    if cfg.output.generate_incidents:
        ensure_dir(root / "incidents")
    if cfg.output.generate_clusters:
        ensure_dir(root / "clusters")
    if cfg.output.generate_chunks:
        ensure_dir(root / "chunks")

    write_readme(root, records)
    write_levels_md(root, records)
    write_timeline_md(root, records, cfg.aggregation.timeline)
    write_top_errors_md(root, records)

    if cfg.output.split_by_level:
        write_raw_by_level(root, records)

    if cfg.output.generate_incidents:
        write_incidents(root, records)

    if cluster_labels is not None and cfg.output.generate_clusters and len(cluster_labels) == len(records):
        write_cluster_files(root, records, cluster_labels)
