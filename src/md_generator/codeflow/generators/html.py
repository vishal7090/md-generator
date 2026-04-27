from __future__ import annotations

import html
import json
from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice


def write_html_bundle(out: Path, entry_id: str, sl: FlowSlice, graph_json: dict) -> None:
    payload = json.dumps(graph_json, ensure_ascii=False)
    title = html.escape(entry_id)
    nodes_text = html.escape("\n".join(sorted(sl.nodes)))
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; display: flex; height: 100vh; }}
    #side {{ width: 280px; border-right: 1px solid #ccc; padding: 8px; overflow: auto; }}
    #cy {{ flex: 1; min-height: 400px; }}
    pre {{ white-space: pre-wrap; font-size: 12px; }}
  </style>
</head>
<body>
  <div id="side">
    <h3>Entry</h3>
    <pre>{html.escape(entry_id)}</pre>
    <h4>Nodes</h4>
    <pre>{nodes_text}</pre>
  </div>
  <div id="cy"></div>
  <script>
    const data = {payload};
    const els = [];
    for (const n of data.nodes || []) {{
      els.push({{ data: {{ id: n.id, label: n.id }}}});
    }}
    for (const e of data.edges || []) {{
      els.push({{ data: {{ id: e.source + "->" + e.target, source: e.source, target: e.target }}}});
    }}
    cytoscape({{
      container: document.getElementById('cy'),
      elements: els,
      style: [
        {{ selector: 'node', style: {{ 'label': 'data(label)', 'font-size': 10 }}}}, 
        {{ selector: 'edge', style: {{ 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'width': 2 }}}}, 
      ],
      layout: {{ name: 'breadthfirst', directed: true }},
    }});
  </script>
</body>
</html>
"""
    out.write_text(body, encoding="utf-8")
