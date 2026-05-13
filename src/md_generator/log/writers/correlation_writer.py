from __future__ import annotations

from pathlib import Path

from md_generator.log.correlation.correlation_engine import build_correlated_requests
from md_generator.log.correlation.correlation_models import CorrelatedRequest
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def write_correlation_artifacts(root: Path, records: list[LogRecord]) -> list[CorrelatedRequest]:
    reqs = build_correlated_requests(records)
    for i, req in enumerate(reqs[:200], start=1):
        lines = [
            f"# Request flow: {req.request_id}",
            "",
            f"- Correlation ID: {req.correlation_id or 'n/a'}",
            f"- Session ID: {req.session_id or 'n/a'}",
            "",
            "## Timeline",
            "",
        ]
        for r in req.records[:100]:
            ts = r.timestamp.isoformat() if r.timestamp else "n/a"
            lines.append(f"- {ts} `{r.level}` {r.message[:400]}")
        write_text(root / "correlation" / f"request_{i:03d}.md", "\n".join(lines) + "\n")
    index = "\n".join(f"- [{r.request_id}](request_{i:03d}.md)" for i, r in enumerate(reqs[:200], start=1))
    write_text(root / "correlation" / "README.md", f"# Correlation index\n\n{index}\n")
    return reqs
