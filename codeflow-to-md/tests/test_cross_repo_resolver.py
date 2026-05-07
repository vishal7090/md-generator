from __future__ import annotations

import networkx as nx

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.cross_repo_resolver import resolve_cross_repo_imports
from md_generator.codeflow.graph.multigraph_utils import edge_payload
from md_generator.codeflow.graph.multi_repo import merge_graphs


def test_resolve_cross_repo_imports_python_hints() -> None:
    g1: nx.MultiDiGraph = nx.MultiDiGraph()
    g2: nx.MultiDiGraph = nx.MultiDiGraph()
    fu = "file:app/main.py"
    ext = "external::com.other.util"
    fb = "file:com/other/util.py"
    g1.add_node(fu, type="file", language="python", repo="aa")
    g1.add_node(ext, type="external", language="python", tags=["external"])
    g2.add_node(fb, type="file", language="python", repo="bb")
    g1.add_edge(
        fu,
        ext,
        **edge_payload(relation=rel.REL_IMPORTS, confidence=0.8, type="structural"),
    )
    merged = merge_graphs([g1, g2], ["aa", "bb"])
    n = merged.number_of_nodes()
    e0 = merged.number_of_edges()
    added = resolve_cross_repo_imports(merged, {"com.other": "bb"})
    assert added == 1
    assert merged.number_of_nodes() == n
    src = "aa::file:app/main.py"
    tgt = "bb::file:com/other/util.py"
    assert merged.has_edge(src, tgt)
    keys = [k for k, d in merged[src][tgt].items() if d.get("relation") == rel.REL_CROSS_REPO_IMPORT]
    assert len(keys) == 1
    assert merged.number_of_edges() == e0 + 1
