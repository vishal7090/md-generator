from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.generators.cytoscape_enrich import enrich_graph_for_views
from md_generator.codeflow.generators.html import write_html_bundle


def test_enrich_adds_depth_preset_cluster(tmp_path: Path) -> None:
    graph = {
        "nodes": [
            {"id": "a", "file_path": "pkg/x.py", "class_name": "X", "method_name": "a"},
            {"id": "b", "file_path": "pkg/y.py", "class_name": "Y", "method_name": "b"},
        ],
        "edges": [{"source": "a", "target": "b", "type": "sync"}],
    }
    out = enrich_graph_for_views(graph, "a")
    assert out["entry_id"] == "a"
    assert len(out["compound_parents"]) == 1
    na = next(n for n in out["nodes"] if n["id"] == "a")
    nb = next(n for n in out["nodes"] if n["id"] == "b")
    assert na["cy_depth"] == 0
    assert nb["cy_depth"] == 1
    assert "cy_preset_x" in na and "cy_cluster_id" in na


def test_write_html_bundle_writes_tabbed_and_standalone(tmp_path: Path) -> None:
    graph = {
        "nodes": [{"id": "e", "type": "entry"}, {"id": "m", "type": "method"}],
        "edges": [{"source": "e", "target": "m", "type": "sync"}],
    }
    sl = FlowSlice(entry_id="e", nodes={"e", "m"}, edges=[], depth=2)
    out = tmp_path / "index.html"
    write_html_bundle(out, "e", sl, graph)
    assert out.is_file()
    d = tmp_path
    assert (d / "graph-view-flow.html").is_file()
    assert (d / "graph-view-layered.html").is_file()
    assert (d / "graph-view-clustered.html").is_file()
    text = out.read_text(encoding="utf-8")
    assert 'data-tab="flow"' in text
    assert "cy-flow" in text and "wireFilterAll" in text
    assert "index.html" in (d / "graph-view-layered.html").read_text(encoding="utf-8")
