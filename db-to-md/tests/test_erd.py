from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from md_generator.db.core.erd.dot_emitter import build_dot, escape_dot_label
from md_generator.db.core.erd.filter import subgraph_full, subgraphs_per_schema, subgraphs_per_table
from md_generator.db.core.erd.model import FKEdge, collect_fk_edges
from md_generator.db.core.erd.mermaid_emitter import build_mermaid_er
from md_generator.db.core.erd.pipeline import count_erd_render_steps, write_erd_outputs
from md_generator.db.core.models import (
    ColumnInfo,
    ForeignKeyInfo,
    TableDetail,
    TableInfo,
)
from md_generator.db.core.run_config import ErdConfig


def _detail(schema: str, name: str, fks: tuple = ()) -> TableDetail:
    return TableDetail(
        table=TableInfo(schema=schema, name=name, comment=None),
        columns=(ColumnInfo("id", "int", False, None, None),),
        primary_key=("id",),
        foreign_keys=fks,
    )


def test_escape_dot_label() -> None:
    assert escape_dot_label('a"b\\c') == 'a\\"b\\\\c'


def test_collect_fk_edges_sorted() -> None:
    b = _detail("public", "b", ())
    a = _detail(
        "public",
        "a",
        (ForeignKeyInfo("fk", ("bid",), "public", "b", ("id",)),),
    )
    edges = collect_fk_edges([b, a])
    assert len(edges) == 1
    assert edges[0].from_table == "a"
    assert edges[0].to_table == "b"


def test_subgraph_full_caps_and_filters_edges() -> None:
    t1 = _detail("s", "t1", ())
    t2 = _detail("s", "t2", (ForeignKeyInfo(None, ("x",), "s", "t1", ("id",)),))
    t3 = _detail("s", "t3", (ForeignKeyInfo(None, ("y",), "s", "t2", ("id",)),))
    details = [t3, t1, t2]
    nodes, edges = subgraph_full(details, max_tables=2)
    assert ("s", "t1") in nodes
    assert ("s", "t2") in nodes
    assert ("s", "t3") not in nodes
    assert all(e.from_key in nodes and e.to_key in nodes for e in edges)


def test_build_dot_snapshot() -> None:
    nodes = frozenset({("public", "a"), ("public", "b")})
    edges = (
        FKEdge("public", "a", "public", "b", "fk_ab", ("bid",), ("id",)),
    )
    dot = build_dot("test_erd", nodes, edges)
    assert 'digraph "test_erd"' in dot
    assert "n0 -> n1" in dot
    assert "bid->id" in dot


@pytest.mark.skipif(not shutil.which("dot"), reason="Graphviz dot not on PATH")
def test_write_erd_outputs_renders_png_svg(tmp_path: Path) -> None:
    a = _detail(
        "public",
        "orders",
        (ForeignKeyInfo("fk_u", ("user_id",), "public", "users", ("id",)),),
    )
    u = _detail("public", "users", ())
    res = write_erd_outputs(tmp_path, [u, a], ErdConfig(max_tables=10, scope="full"), on_step=None)
    assert res.engine == "graphviz"
    assert any(p.endswith("erd/full.png") for p in res.artifacts)
    png = tmp_path / "erd" / "full.png"
    assert png.is_file() and png.stat().st_size > 0
    svg = tmp_path / "erd" / "full.svg"
    assert svg.is_file() and svg.stat().st_size > 0


def test_build_mermaid_er_snapshot() -> None:
    nodes = frozenset({("public", "a"), ("public", "b")})
    edges = (FKEdge("public", "a", "public", "b", "fk_ab", ("bid",), ("id",)),)
    src = build_mermaid_er("t", nodes, edges)
    assert "erDiagram" in src
    assert "E1 ||--o{ E0" in src


def test_count_erd_render_steps_respects_dot_flag() -> None:
    u = _detail("public", "u", ())
    assert count_erd_render_steps([u], ErdConfig(scope="full"), dot_available=True) == 3
    assert count_erd_render_steps([u], ErdConfig(scope="full"), dot_available=False) == 4


def test_write_erd_outputs_mermaid_when_no_dot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "md_generator.db.core.erd.pipeline.try_resolve_dot_executable",
        lambda: None,
    )
    a = _detail(
        "public",
        "orders",
        (ForeignKeyInfo("fk_u", ("user_id",), "public", "users", ("id",)),),
    )
    u = _detail("public", "users", ())
    res = write_erd_outputs(tmp_path, [u, a], ErdConfig(max_tables=10, scope="full"), on_step=None)
    assert res.engine in ("mermaid_py", "mermaid_text")
    mmd = tmp_path / "erd" / "full.mermaid"
    assert mmd.is_file()
    assert "erDiagram" in mmd.read_text(encoding="utf-8")
    assert (tmp_path / "erd" / "full.md").is_file()


def test_subgraphs_per_schema_deterministic_order() -> None:
    a = _detail("s2", "a", ())
    b = _detail("s1", "b", ())
    subs = subgraphs_per_schema([a, b], max_tables=10)
    assert [x[0] for x in subs] == ["s1", "s2"]


def test_subgraphs_per_table_ego_includes_neighbor() -> None:
    users = _detail("public", "users", ())
    orders = _detail(
        "public",
        "orders",
        (ForeignKeyInfo("fk", ("user_id",), "public", "users", ("id",)),),
    )
    subs = subgraphs_per_table([orders, users], max_tables=1)
    assert len(subs) == 1
    _, nodes, edges = subs[0]
    assert ("public", "orders") in nodes
    assert ("public", "users") in nodes
    assert len(edges) >= 1
