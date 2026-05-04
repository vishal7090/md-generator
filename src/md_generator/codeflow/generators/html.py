"""Cytoscape-based HTML bundles: tabbed ``index.html`` plus standalone view files."""

from __future__ import annotations

import html
import json
from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.generators.cytoscape_enrich import enrich_graph_for_views


def _payload(graph_json: dict, entry_id: str) -> str:
    return json.dumps(enrich_graph_for_views(graph_json, entry_id), ensure_ascii=False)


def _shared_css() -> str:
    return """
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; }
    header { border-bottom: 1px solid #ccc; padding: 8px 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    header h1 { font-size: 1rem; margin: 0; flex: 1; min-width: 200px; }
    .tabs { display: flex; gap: 4px; flex-wrap: wrap; }
    .tabs button {
      padding: 6px 12px; border: 1px solid #bbb; background: #f4f4f4; cursor: pointer; border-radius: 4px; font-size: 13px;
    }
    .tabs button.active { background: #1a5fb4; color: #fff; border-color: #1a5fb4; }
    .toolbar { display: flex; align-items: center; gap: 8px; margin-left: auto; }
    .toolbar input { padding: 6px 8px; min-width: 180px; border: 1px solid #ccc; border-radius: 4px; }
    main { flex: 1; display: flex; min-height: 0; }
    #side { width: 260px; border-right: 1px solid #ccc; padding: 8px; overflow: auto; font-size: 12px; }
    .cy-wrap { flex: 1; min-width: 0; position: relative; display: none; }
    .cy-wrap.active { display: block; }
    .cy { width: 100%; height: 100%; min-height: 360px; }
    pre { white-space: pre-wrap; margin: 0; }
    """


def _shared_js_core() -> str:
    """Cytoscape helpers: elements builder, styles, filter. Uses global DATA and ENTRY."""
    return r"""
    function buildElements(data, withCompound) {
      const els = [];
      if (withCompound && data.compound_parents) {
        for (const p of data.compound_parents) {
          els.push({ data: { id: p.id, label: p.label }, classes: 'cluster' });
        }
      }
      for (const n of data.nodes || []) {
        const d = { id: n.id, label: n.cy_label_short || n.id };
        if (withCompound && n.cy_cluster_id) d.parent = n.cy_cluster_id;
        const cls = (n.type === 'entry' ? 'entry ' : '') + (n.unresolved ? 'unresolved' : '');
        els.push({ data: d, classes: cls.trim() });
      }
      for (const e of data.edges || []) {
        if (!e.source || !e.target) continue;
        els.push({
          data: {
            id: e.source + '->' + e.target,
            source: e.source,
            target: e.target,
          },
        });
      }
      return els;
    }

    function baseStyles() {
      return [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 10,
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            width: 'label',
            height: 'label',
            padding: '8px',
            'background-color': '#ddd',
            'border-width': 1,
            'border-color': '#888',
          },
        },
        { selector: 'node.dim', style: { opacity: 0.14, 'text-opacity': 0.2 } },
        { selector: 'node.entry', style: { 'background-color': '#8fd', 'border-color': '#063', 'font-weight': 'bold' } },
        { selector: 'node.unresolved', style: { 'background-color': '#fdd' } },
        { selector: 'node:parent', style: {
            'background-opacity': 0.12,
            'border-width': 1,
            'border-color': '#999',
            'border-style': 'dashed',
            label: 'data(label)',
            'font-size': 11,
            'text-valign': 'top',
            'text-halign': 'center',
            'text-margin-y': '-6px',
            padding: '14px',
          },
        },
        { selector: 'node.cluster', style: { 'background-color': '#e8eef5' } },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            width: 2,
            'line-color': '#555',
            'target-arrow-color': '#555',
          },
        },
      ];
    }

    function applyFilter(cy, q) {
      const needle = (q || '').trim().toLowerCase();
      cy.batch(() => {
        cy.elements().removeClass('dim');
        if (!needle) return;
        cy.nodes().forEach((n) => {
          const lab = (n.data('label') || n.id() || '').toLowerCase();
          if (!lab.includes(needle)) n.addClass('dim');
        });
      });
    }

    function wireFilter(cy, inputId) {
      const inp = document.getElementById(inputId);
      if (!inp) return;
      inp.addEventListener('input', () => applyFilter(cy, inp.value));
    }

    window.__codeflowCyInstances = window.__codeflowCyInstances || [];
    function registerCy(cy) {
      window.__codeflowCyInstances.push(cy);
    }
    function wireFilterAll(inputId) {
      const inp = document.getElementById(inputId);
      if (!inp) return;
      inp.addEventListener('input', () => {
        const q = inp.value;
        (window.__codeflowCyInstances || []).forEach((cy) => applyFilter(cy, q));
      });
    }
    """


def _init_cytoscape_flow(containerId: str, *, register: bool, filter_input_id: str) -> str:
    tail = "registerCy(cy);" if register else f"wireFilter(cy, '{filter_input_id}');"
    return rf"""
    (function() {{
      const els = buildElements(DATA, false);
      const cy = cytoscape({{
        container: document.getElementById('{containerId}'),
        elements: els,
        style: baseStyles(),
        layout: {{ name: 'breadthfirst', directed: true, roots: ENTRY ? [ENTRY] : undefined, spacingFactor: 1.2 }},
        wheelSensitivity: 0.35,
      }});
      {tail}
    }})();
    """


def _init_cytoscape_layered(containerId: str, *, register: bool, filter_input_id: str) -> str:
    tail = "registerCy(cy);" if register else f"wireFilter(cy, '{filter_input_id}');"
    return rf"""
    (function() {{
      const nodeById = new Map((DATA.nodes || []).map((n) => [n.id, n]));
      const els = buildElements(DATA, false).map((el) => {{
        if (!el.data || el.data.source) return el;
        const row = nodeById.get(el.data.id);
        if (row && typeof row.cy_preset_x === 'number') {{
          return {{ ...el, position: {{ x: row.cy_preset_x, y: row.cy_preset_y }} }};
        }}
        return el;
      }});
      const cy = cytoscape({{
        container: document.getElementById('{containerId}'),
        elements: els,
        style: baseStyles(),
        layout: {{ name: 'preset' }},
        wheelSensitivity: 0.35,
      }});
      {tail}
    }})();
    """


def _init_cytoscape_clustered(containerId: str, *, register: bool, filter_input_id: str) -> str:
    tail = "registerCy(cy);" if register else f"wireFilter(cy, '{filter_input_id}');"
    return rf"""
    (function() {{
      const els = buildElements(DATA, true);
      const cy = cytoscape({{
        container: document.getElementById('{containerId}'),
        elements: els,
        style: baseStyles(),
        layout: {{ name: 'cose', animate: false, nodeRepulsion: 8000, idealEdgeLength: 100, componentSpacing: 40 }},
        wheelSensitivity: 0.35,
      }});
      {tail}
    }})();
    """


def write_html_bundle(out: Path, entry_id: str, sl: FlowSlice, graph_json: dict) -> None:
    """Write tabbed ``index.html`` and standalone ``graph-view-*.html`` files in the same directory."""
    payload = _payload(graph_json, entry_id)
    title = html.escape(entry_id)
    nodes_text = html.escape("\n".join(sorted(sl.nodes)))
    entry_json = json.dumps(entry_id, ensure_ascii=False)

    side_block = f"""
    <div id="side">
      <h3>Entry</h3>
      <pre>{html.escape(entry_id)}</pre>
      <p style="font-size:12px;margin:8px 0;"><a href="entry.md">entry.md</a> · <a href="flow.md">flow.md</a> (if generated)</p>
      <h4>Nodes ({len(sl.nodes)})</h4>
      <pre>{nodes_text}</pre>
      <p style="margin-top:12px;color:#555;font-size:11px;">Flow: breadth-first from entry. Layered: BFS rank positions (NetworkX). Clustered: package/dir compound groups + COSE.</p>
    </div>"""

    # Tabbed index.html
    index_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  <style>{_shared_css()}</style>
</head>
<body>
  <header>
    <h1>Codeflow: {title}</h1>
    <div class="tabs" id="tabbar">
      <button type="button" class="active" data-tab="flow">Flow</button>
      <button type="button" data-tab="layered">Layered</button>
      <button type="button" data-tab="clustered">Clustered</button>
    </div>
    <div class="toolbar">
      <label for="flt">Filter</label>
      <input type="search" id="flt" placeholder="id / label substring…" autocomplete="off"/>
    </div>
  </header>
  <main>
    {side_block}
    <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
      <div class="cy-wrap active" data-tab="flow"><div id="cy-flow" class="cy"></div></div>
      <div class="cy-wrap" data-tab="layered"><div id="cy-layered" class="cy"></div></div>
      <div class="cy-wrap" data-tab="clustered"><div id="cy-clustered" class="cy"></div></div>
    </div>
  </main>
  <script>
    const DATA = {payload};
    const ENTRY = {entry_json};
    {_shared_js_core()}
    window.__codeflowCyInstances = [];
    {_init_cytoscape_flow("cy-flow", register=True, filter_input_id="flt")}
    {_init_cytoscape_layered("cy-layered", register=True, filter_input_id="flt")}
    {_init_cytoscape_clustered("cy-clustered", register=True, filter_input_id="flt")}
    wireFilterAll('flt');
    document.querySelectorAll('#tabbar button').forEach((btn) => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('#tabbar button').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.getAttribute('data-tab');
        document.querySelectorAll('.cy-wrap').forEach((w) => {{
          w.classList.toggle('active', w.getAttribute('data-tab') === tab);
        }});
        window.dispatchEvent(new Event('resize'));
      }});
    }});
  </script>
</body>
</html>
"""
    out.write_text(index_body, encoding="utf-8")

    base = out.parent
    _write_standalone_view(
        base / "graph-view-flow.html",
        title + " — flow",
        payload,
        "flow",
        entry_id,
        nodes_text,
    )
    _write_standalone_view(
        base / "graph-view-layered.html",
        title + " — layered",
        payload,
        "layered",
        entry_id,
        nodes_text,
    )
    _write_standalone_view(
        base / "graph-view-clustered.html",
        title + " — clustered",
        payload,
        "clustered",
        entry_id,
        nodes_text,
    )


def _write_standalone_view(
    path: Path,
    page_title: str,
    payload: str,
    mode: str,
    entry_id: str,
    nodes_text: str,
) -> None:
    esc_title = html.escape(page_title)
    entry_json = json.dumps(entry_id, ensure_ascii=False)
    if mode == "flow":
        init = _init_cytoscape_flow("cy-main", register=False, filter_input_id="flt")
    elif mode == "layered":
        init = _init_cytoscape_layered("cy-main", register=False, filter_input_id="flt")
    else:
        init = _init_cytoscape_clustered("cy-main", register=False, filter_input_id="flt")

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{esc_title}</title>
  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  <style>
    {_shared_css()}
    main {{ flex-direction: column; }}
    #side {{ width: 100%; max-height: 140px; border-right: none; border-bottom: 1px solid #ccc; }}
    .cy-wrap.active {{ flex: 1; }}
  </style>
</head>
<body>
  <header>
    <h1>{esc_title}</h1>
    <div class="toolbar">
      <a href="index.html" style="font-size:13px;margin-right:8px;">Tabbed bundle</a>
      <label for="flt">Filter</label>
      <input type="search" id="flt" placeholder="id / label…" autocomplete="off"/>
    </div>
  </header>
  <main>
    <div id="side">
      <h4 style="margin:0 0 4px 0;">Nodes</h4>
      <pre style="max-height:100px;overflow:auto;">{nodes_text}</pre>
    </div>
    <div class="cy-wrap active" style="display:block;"><div id="cy-main" class="cy"></div></div>
  </main>
  <script>
    const DATA = {payload};
    const ENTRY = {entry_json};
    {_shared_js_core()}
    {init}
  </script>
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")
