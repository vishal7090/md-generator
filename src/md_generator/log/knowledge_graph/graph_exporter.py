from __future__ import annotations

import json
from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.knowledge_graph.graph_builder import build_graph
from md_generator.log.parser.models import LogRecord
from md_generator.log.utils.io import write_text


def export_graph(root: Path, records: list[LogRecord], cfg: LogRunConfig) -> None:
    nodes, edges = build_graph(records)
    write_text(
        root / "graphs" / "edges.json",
        json.dumps(
            [{"source": e.source_id, "target": e.target_id, "relation": e.relation} for e in edges],
            indent=2,
        )
        + "\n",
    )
    lines = ["# Telemetry graph", "", f"Nodes: {len(nodes)}", f"Edges: {len(edges)}", ""]
    if cfg.knowledge_graph.mermaid:
        lines.extend(["```mermaid", "graph TD"])
        for e in edges:
            lines.append(f"  {e.source_id.replace(':', '_')} --> {e.target_id.replace(':', '_')}")
        lines.append("```")
    write_text(root / "graphs" / "summary.md", "\n".join(lines) + "\n")
