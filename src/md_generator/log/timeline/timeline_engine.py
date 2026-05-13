from __future__ import annotations

from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord
from md_generator.log.timeline.causal_chain import infer_causal_chain
from md_generator.log.timeline.ordering import order_events
from md_generator.log.utils.io import write_text


def write_timeline_artifacts(
    root: Path,
    records: list[LogRecord],
    incidents: list[Incident],
    cfg: LogRunConfig,
) -> None:
    events = order_events(records)
    chain = infer_causal_chain(events, cfg.timeline.causal_window_seconds)
    title = incidents[0].title if incidents else "Operational timeline"
    lines = [f"# Timeline: {title}", ""]
    for step in chain:
        lines.append(step)
    write_text(root / "timeline" / "reconstruction.md", "\n".join(lines) + "\n")
