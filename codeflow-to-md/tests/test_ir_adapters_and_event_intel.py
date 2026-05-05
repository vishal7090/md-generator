from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from md_generator.codeflow.analyzers.flow_analyzer import slice_from_entry, walk_with_depth
from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.analysis import event_impact, reference_impact
from md_generator.codeflow.graph.event_graph import apply_event_edges
from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
from md_generator.codeflow.graph.multigraph_utils import edge_payload
from md_generator.codeflow.graph.query_engine import execute_query
from md_generator.codeflow.models.ir import EntryKind, EntryRecord, FileParseResult
from md_generator.codeflow.parsers.adapters.ir_from_dump import ir_methods_from_dump_doc


def test_ir_from_dump_doc_to_cfg() -> None:
    doc = {
        "irVersion": 1,
        "funcs": [
            {
                "id": "pkg/x.go::main",
                "body": [
                    {
                        "kind": "IF",
                        "condition": "err != nil",
                        "body": [{"kind": "RETURN", "label": "return err", "line": 2}],
                        "else_body": [],
                    },
                ],
            },
        ],
    }
    methods = ir_methods_from_dump_doc(doc, file_path="/tmp/x.go", language="go")
    assert len(methods) == 1
    assert methods[0].body[0].kind == "IF"
    cfg = build_cfg_from_ir(methods[0], max_nodes=100)
    kinds = {n.kind for n in cfg.nodes.values()}
    assert "START" in kinds and "END" in kinds


def test_query_engine_event_and_union() -> None:
    g = nx.MultiDiGraph()
    g.add_node("A")
    g.add_node("B")
    g.add_node("topic:t")
    g.add_edge("A", "topic:t", **edge_payload(relation=rel.REL_EVENT, event_role="producer", confidence=0.5))
    g.add_edge("topic:t", "B", **edge_payload(relation=rel.REL_EVENT, event_role="consumer", confidence=0.9))
    rows_e = execute_query(g, "MATCH (a)-[EVENT]->(b)")
    assert len(rows_e) == 2
    rows_u = execute_query(g, "MATCH (a)-[CALLS|EVENT]->(b)")
    assert len(rows_u) == 2


def test_event_impact_reachability() -> None:
    g = nx.MultiDiGraph()
    for n in ("M1", "topic:x", "M2", "M3"):
        g.add_node(n)
    g.add_edge("M1", "topic:x", **edge_payload(relation=rel.REL_EVENT, event_role="producer"))
    g.add_edge("topic:x", "M2", **edge_payload(relation=rel.REL_EVENT, event_role="consumer"))
    g.add_edge("M2", "M3", **edge_payload(relation=rel.REL_CALLS))
    imp = event_impact(g, "M1", cap=20)
    assert "topic:x" in imp
    assert "M2" in imp
    assert "M3" in imp


def test_reference_impact_direct() -> None:
    g = nx.MultiDiGraph()
    g.add_node("A")
    g.add_node("Repo")
    g.add_edge("A", "Repo", **edge_payload(relation=rel.REL_REFERENCES, confidence=0.7))
    assert reference_impact(g, "A", cap=10) == ["Repo"]


def test_flow_walk_includes_event_when_configured() -> None:
    g = nx.MultiDiGraph()
    g.add_node("E")
    g.add_node("topic:z")
    g.add_edge("E", "topic:z", **edge_payload(relation=rel.REL_EVENT, event_role="producer"))
    rels = frozenset({rel.REL_CALLS, rel.REL_EVENT})
    nodes, edges, _, _ = walk_with_depth(g, "E", 3, relations=rels)
    assert "topic:z" in nodes
    assert any(u == "E" and v == "topic:z" for u, v, _ in edges)


def test_slice_from_entry_with_event_relation(tmp_path: Path) -> None:
    g = nx.MultiDiGraph()
    g.add_node("E")
    g.add_node("topic:z")
    g.add_edge("E", "topic:z", **edge_payload(relation=rel.REL_EVENT, event_role="producer"))
    sl = slice_from_entry(g, "E", 2, relations=frozenset({rel.REL_CALLS, rel.REL_EVENT}))
    assert any(v == "topic:z" for _u, v, _ in sl.edges)


def test_apply_event_edges_kafka_listener(tmp_path: Path) -> None:
    p = tmp_path / "Foo.java"
    p.write_text(
        "import org.springframework.kafka.annotation.KafkaListener;\n"
        "class Foo { @KafkaListener(topics = \"orders\") void listen() {} }\n",
        encoding="utf-8",
    )
    key = p.relative_to(tmp_path).as_posix()
    sym = f"{key}::Foo.listen"
    g = nx.MultiDiGraph()
    g.add_node(sym, id=sym, type="method")
    pr = FileParseResult(
        path=p,
        language="java",
        entries=[
            EntryRecord(
                symbol_id=sym,
                kind=EntryKind.KAFKA,
                label="@KafkaListener",
                file_path=str(p),
                line=2,
            ),
        ],
    )
    apply_event_edges(g, [pr])
    assert g.has_node("topic:orders")
    assert g.has_edge("topic:orders", sym)
