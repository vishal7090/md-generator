"""Single-page unified view: Cytoscape flow graph, CFG Mermaid, semantic sidebar."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.generators.cytoscape_enrich import enrich_graph_for_views


def _payload(graph_json: dict, entry_id: str) -> str:
    return json.dumps(enrich_graph_for_views(graph_json, entry_id), ensure_ascii=False)


def write_html_unified(
    entry_dir: Path,
    entry_id: str,
    sl: FlowSlice,
    graph_json: dict,
    *,
    cfg_mermaid_text: str | None,
    semantic_neighbors: dict[str, Any] | None,
    search_hits: list[dict[str, Any]] | None,
    cluster_mode_note: str,
    semantic_search_results_href: str | None = None,
    nl_query_href: str | None = None,
    runtime_insights: dict[str, Any] | None = None,
    pr_impact: dict[str, Any] | None = None,
) -> None:
    """Write ``index.unified.html`` under ``entry_dir``."""
    payload = _payload(graph_json, entry_id)
    title = html.escape(entry_id)
    entry_json = json.dumps(entry_id, ensure_ascii=False)
    neighbors_json = json.dumps(semantic_neighbors or {}, ensure_ascii=False)
    search_json = json.dumps(search_hits or [], ensure_ascii=False)
    cluster_esc = html.escape(cluster_mode_note)
    mmd_block = cfg_mermaid_text.strip() if cfg_mermaid_text else ""
    search_link = ""
    if semantic_search_results_href:
        sh = html.escape(semantic_search_results_href)
        search_link = f'<a href="{sh}" style="font-size:12px;">search hits</a>'
    nl_link = ""
    if nl_query_href:
        nh = html.escape(nl_query_href)
        nl_link = f'<a href="{nh}" style="font-size:12px;">nl-query-results.json</a>'
    ri_json = json.dumps(runtime_insights or {}, ensure_ascii=False)
    pr_json = json.dumps(pr_impact or {}, ensure_ascii=False)

    # Collect semantic_group values present in slice
    groups: set[int] = set()
    for n in graph_json.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        sg = n.get("semantic_group")
        if isinstance(sg, int):
            groups.add(sg)
    group_options = "".join(
        f'<option value="{g}">Group {g}</option>' for g in sorted(groups)
    )

    repos: set[str] = set()
    for n in graph_json.get("nodes") or []:
        if isinstance(n, dict) and n.get("repo"):
            repos.add(str(n["repo"]))
    repo_options = "".join(
        f'<option value="{html.escape(r)}">{html.escape(r)}</option>' for r in sorted(repos)
    )

    nodes_text = html.escape("\n".join(sorted(sl.nodes)))

    css = """
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; }
    header { border-bottom: 1px solid #ccc; padding: 8px 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    header h1 { font-size: 1rem; margin: 0; flex: 1; min-width: 200px; }
    .toolbar { display: flex; align-items: center; gap: 8px; margin-left: auto; flex-wrap: wrap; }
    .toolbar input, .toolbar select { padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
    main { flex: 1; display: flex; min-height: 0; }
    #left { width: 280px; border-right: 1px solid #ccc; padding: 8px; overflow: auto; font-size: 12px; display: flex; flex-direction: column; gap: 8px; }
    #cy-wrap { flex: 1; min-width: 0; position: relative; }
    #cy { width: 100%; height: 100%; min-height: 320px; }
    #right { width: 340px; border-left: 1px solid #ccc; padding: 8px; overflow: auto; font-size: 12px; display: flex; flex-direction: column; gap: 8px; }
    pre { white-space: pre-wrap; margin: 0; font-size: 11px; }
    .mermaid { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; }
    #simList button { display: block; width: 100%; text-align: left; margin: 2px 0; padding: 4px 6px; font-size: 11px; cursor: pointer; border: 1px solid #ccc; border-radius: 3px; background: #fff; }
    #simList button:hover { background: #eef6ff; }
    .hit { box-shadow: 0 0 0 3px #f90 !important; }
    """

    js_core = r"""
    function relKey(e) {
      const r = (e && e.relation) || (e && e.kind) || '';
      return String(r).toUpperCase();
    }
    function buildElements(data) {
      const els = [];
      const HITS = new Set((SEARCH_HITS || []).map((h) => h.node_id));
      const PR_SEEDS = new Set((PR_IMPACT && PR_IMPACT.seed_nodes) || []);
      const PR_IMP = new Set((PR_IMPACT && PR_IMPACT.impacted_nodes) || []);
      for (const n of data.nodes || []) {
        const d = { id: n.id, label: n.cy_label_short || n.id, semantic_group: n.semantic_group, repo: n.repo || '' };
        let prCls = '';
        if (PR_SEEDS.size && PR_SEEDS.has(n.id)) prCls = 'pr-seed ';
        else if (PR_IMP.size && PR_IMP.has(n.id)) prCls = 'pr-impacted ';
        const cls = (n.type === 'entry' ? 'entry ' : '') + (n.unresolved ? 'unresolved ' : '') + (HITS.has(n.id) ? 'hit ' : '') + prCls;
        const row = nodeById.get(n.id);
        if (row && typeof row.cy_preset_x === 'number') {
          els.push({ data: d, classes: cls.trim(), position: { x: row.cy_preset_x, y: row.cy_preset_y } });
        } else {
          els.push({ data: d, classes: cls.trim() });
        }
      }
      let ei = 0;
      for (const e of data.edges || []) {
        if (!e.source || !e.target) continue;
        const rk = relKey(e);
        let lineStyle = 'solid';
        let width = 2;
        if (rk === 'EVENT') { lineStyle = 'dashed'; width = 2; }
        else if (rk === 'REFERENCES') { lineStyle = 'dotted'; width = 2; }
        const eid = 'e' + (ei++);
        els.push({
          data: {
            id: eid,
            source: e.source,
            target: e.target,
            relation: rk,
          },
          classes: rk,
        });
      }
      return els;
    }
    function semanticHue(g) {
      if (g === undefined || g === null || g === '') return '#dddddd';
      const x = Number(g);
      const h = (x * 137.508) % 360;
      return 'hsl(' + h.toFixed(0) + ', 55%, 82%)';
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
            'background-color': (ele) => semanticHue(ele.data('semantic_group')),
            'border-width': 1,
            'border-color': '#888',
          },
        },
        { selector: 'node.dim', style: { opacity: 0.12, 'text-opacity': 0.15 } },
        { selector: 'node.entry', style: { 'border-width': 2, 'border-color': '#063', 'font-weight': 'bold' } },
        { selector: 'node.unresolved', style: { 'border-color': '#c00' } },
        { selector: 'node.hit', style: { 'border-width': 3, 'border-color': '#f90' } },
        { selector: 'node.pr-seed', style: { 'border-width': 4, 'border-color': '#06c' } },
        { selector: 'node.pr-impacted', style: { 'border-width': 2, 'border-color': '#080' } },
        { selector: 'node.dim-pr', style: { opacity: 0.11, 'text-opacity': 0.14 } },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            width: 2,
            'line-color': '#555',
            'target-arrow-color': '#555',
            'line-style': 'solid',
          },
        },
        { selector: 'edge.EVENT', style: { 'line-style': 'dashed' } },
        { selector: 'edge.REFERENCES', style: { 'line-style': 'dotted' } },
      ];
    }
    function applySemanticFilter(cy, groupVal) {
      cy.batch(() => {
        cy.nodes().removeClass('dim');
        if (groupVal === '' || groupVal === '__all__') return;
        const want = String(groupVal);
        cy.nodes().forEach((n) => {
          const g = n.data('semantic_group');
          if (g === undefined || g === null) { n.addClass('dim'); return; }
          if (String(g) !== want) n.addClass('dim');
        });
      });
    }
    function applyTextFilter(cy, q) {
      const needle = (q || '').trim().toLowerCase();
      cy.batch(() => {
        cy.nodes().removeClass('dim');
        if (!needle) return;
        cy.nodes().forEach((n) => {
          const lab = (n.data('label') || n.id() || '').toLowerCase();
          if (!lab.includes(needle)) n.addClass('dim');
        });
      });
    }
    function applyRepoFilter(cy, repoVal) {
      cy.batch(() => {
        cy.nodes().removeClass('dim');
        if (!repoVal || repoVal === '__all__') return;
        cy.nodes().forEach((n) => {
          const r = n.data('repo') || '';
          if (String(r) !== String(repoVal)) n.addClass('dim');
        });
      });
    }
    function applyPrDim(cy, on) {
      cy.batch(() => {
        cy.nodes().removeClass('dim-pr');
        if (!on) return;
        const PR_IMP = new Set((PR_IMPACT && PR_IMPACT.impacted_nodes) || []);
        if (!PR_IMP.size) return;
        cy.nodes().forEach((n) => {
          if (!PR_IMP.has(n.id())) n.addClass('dim-pr');
        });
      });
    }
    """

    mermaid_script = ""
    mermaid_init = "/* no cfg mermaid */"
    if mmd_block:
        mermaid_script = (
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>'
        )
        mermaid_init = r"""
    (async function() {
      const el = document.getElementById('mmd');
      if (!el || !MERMAID_TEXT || !window.mermaid) return;
      el.textContent = MERMAID_TEXT;
      mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
      await mermaid.run({ nodes: [el] });
    })();
    """

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Unified — {title}</title>
  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  {mermaid_script}
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>Codeflow unified · {title}</h1>
    <p style="margin:0;font-size:12px;color:#555;">{cluster_esc}</p>
    <div class="toolbar">
      <label>Semantic group</label>
      <select id="grp">
        <option value="__all__">All</option>
        {group_options}
      </select>
      <label for="flt">Filter</label>
      <input type="search" id="flt" placeholder="label…" autocomplete="off"/>
      <label for="repoF">Repo</label>
      <select id="repoF">
        <option value="__all__">All</option>
        {repo_options}
      </select>
      <label id="prLab" style="display:none;"><input type="checkbox" id="prHi"/> PR focus</label>
      <a href="entry.md" style="font-size:12px;">entry.md</a>
      <a href="semantic-neighbors.json" style="font-size:12px;">neighbors.json</a>
      {search_link}
      {nl_link}
    </div>
  </header>
  <main>
    <div id="left">
      <strong>Slice nodes ({len(sl.nodes)})</strong>
      <pre style="max-height:180px;overflow:auto;">{nodes_text}</pre>
      <strong>Hot paths (CFG+runtime)</strong>
      <pre id="hotPre" style="max-height:100px;overflow:auto;font-size:10px;"></pre>
      <strong>Rare CFG edges</strong>
      <pre id="anoPre" style="max-height:100px;overflow:auto;font-size:10px;"></pre>
      <strong>Similar (embedding)</strong>
      <div id="simList"></div>
    </div>
    <div id="cy-wrap"><div id="cy"></div></div>
    <div id="right">
      <strong>CFG (Mermaid)</strong>
      <div id="mmd" class="mermaid"></div>
      <p style="color:#666;font-size:11px;">Select a node in the graph to focus. Edge styles: CALLS solid, EVENT dashed, REFERENCES dotted.</p>
    </div>
  </main>
  <script>
    const DATA = {payload};
    const ENTRY = {entry_json};
    const NEIGHBORS = {neighbors_json};
    const SEARCH_HITS = {search_json};
    const RUNTIME_INSIGHTS = {ri_json};
    const PR_IMPACT = {pr_json};
    const MERMAID_TEXT = {json.dumps(mmd_block)};
    const nodeById = new Map((DATA.nodes || []).map((n) => [n.id, n]));
    {js_core}
    (function() {{
      const els = buildElements(DATA);
      const cy = cytoscape({{
        container: document.getElementById('cy'),
        elements: els,
        style: baseStyles(),
        layout: {{ name: 'preset' }},
        wheelSensitivity: 0.35,
      }});
      const sim = document.getElementById('simList');
      if (sim && NEIGHBORS && NEIGHBORS.top_k) {{
        NEIGHBORS.top_k.forEach((row) => {{
          const b = document.createElement('button');
          const lab = row.name && row.class_name ? (row.class_name + '.' + row.name) : row.node_id;
          b.textContent = (row.score !== undefined ? row.score.toFixed(3) + ' · ' : '') + lab;
          b.addEventListener('click', () => {{
            const n = cy.getElementById(row.node_id);
            if (n.length) cy.animate({{ fit: {{ eles: n, padding: 40 }}, duration: 200 }});
          }});
          sim.appendChild(b);
        }});
      }}
      document.getElementById('grp').addEventListener('change', (ev) => {{
        applySemanticFilter(cy, ev.target.value);
      }});
      document.getElementById('flt').addEventListener('input', (ev) => {{
        applyTextFilter(cy, ev.target.value);
      }});
      const repoSel = document.getElementById('repoF');
      if (repoSel) {{
        repoSel.addEventListener('change', (ev) => {{
          applyRepoFilter(cy, ev.target.value);
        }});
      }}
      const prCb = document.getElementById('prHi');
      const prLab = document.getElementById('prLab');
      if (prCb && prLab && PR_IMPACT && (PR_IMPACT.impacted_nodes || []).length) {{
        prLab.style.display = '';
        prCb.addEventListener('change', () => {{
          applyPrDim(cy, prCb.checked);
        }});
      }}
      cy.on('tap', 'node', (evt) => {{
        const id = evt.target.id();
        cy.nodes().removeClass('hit');
        evt.target.addClass('hit');
      }});
      const hpEl = document.getElementById('hotPre');
      if (hpEl && RUNTIME_INSIGHTS && RUNTIME_INSIGHTS.hot_paths && RUNTIME_INSIGHTS.hot_paths.length) {{
        hpEl.textContent = RUNTIME_INSIGHTS.hot_paths.map((r, i) =>
          (i + 1) + '. score=' + (r.score || 0) + ' ' + (r.nodes || []).join(' → ')
        ).join('\\n');
      }}
      const apEl = document.getElementById('anoPre');
      if (apEl && RUNTIME_INSIGHTS && RUNTIME_INSIGHTS.rare_cfg_edges && RUNTIME_INSIGHTS.rare_cfg_edges.length) {{
        apEl.textContent = RUNTIME_INSIGHTS.rare_cfg_edges.slice(0, 15).map((e) =>
          e.source + '→' + e.target + ' f=' + (e.frequency !== undefined ? e.frequency : '?')
        ).join('\\n');
      }}
    }})();
    {mermaid_init}
  </script>
</body>
</html>
"""
    (entry_dir / "index.unified.html").write_text(body, encoding="utf-8")
