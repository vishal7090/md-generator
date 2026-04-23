from __future__ import annotations

from pathlib import Path

from md_generator.graph.core.job_manager import GraphJobManager
from md_generator.graph.core.run_config import GraphRunConfig


def test_graph_job_create_and_load_config(tmp_path: Path) -> None:
    cfg = GraphRunConfig(
        source="neo4j",
        uri="bolt://localhost:7687",
        user="neo4j",
        password="x",
        graph_file=None,
        max_nodes=10,
        max_edges=10,
    ).normalized()
    jm = GraphJobManager(in_memory=True, workspace_root=tmp_path / "ws")
    rec = jm.create_job(cfg)
    loaded = jm.load_config(rec.job_id)
    assert loaded is not None
    assert loaded.source == "neo4j"
    assert loaded.uri == "bolt://localhost:7687"
    jm.close()
