from __future__ import annotations

from collections import Counter
from pathlib import Path

from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_service_reports(out: Path, records: list[LogRecord]) -> None:
    by_svc: Counter[str] = Counter()
    for r in records:
        svc = str((r.metadata or {}).get("service") or r.logger or "unknown")
        by_svc[svc] += 1
    doc_dir = out / "documentation" / "services"
    doc_dir.mkdir(parents=True, exist_ok=True)
    for svc, count in by_svc.most_common(100):
        safe = svc.replace("/", "_")[:80]
        write_text(doc_dir / f"{safe}.md", f"# Service: {svc}\n\nLog records: {count}\n")
