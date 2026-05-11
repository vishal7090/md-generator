from __future__ import annotations

from pathlib import Path

from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_cluster_files(root: Path, records: list[LogRecord], labels: list[int]) -> None:
    by_c: dict[int, list[LogRecord]] = {}
    for r, lab in zip(records, labels):
        by_c.setdefault(int(lab), []).append(r)
    for c_id, rs in sorted(by_c.items()):
        lines = [f"# Cluster {c_id}", "", f"**Size:** {len(rs)}", "", "## Samples", ""]
        for r in rs[:15]:
            lines.append(f"- `{r.level}` {r.message[:400].replace(chr(10), ' ')}")
        write_text(root / "clusters" / f"cluster_{c_id:03d}.md", "\n".join(lines) + "\n")
