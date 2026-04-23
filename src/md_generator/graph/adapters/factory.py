from __future__ import annotations

from md_generator.graph.adapters.networkx_adapter import NetworkXAdapter
from md_generator.graph.core.base_adapter import BaseAdapter
from md_generator.graph.core.run_config import GraphRunConfig


def create_adapter(cfg: GraphRunConfig) -> BaseAdapter:
    src = cfg.source
    if src == "networkx":
        return NetworkXAdapter(graph=None, graph_file=cfg.graph_file)
    if src == "neo4j":
        from md_generator.graph.adapters.neo4j_adapter import Neo4jAdapter

        return Neo4jAdapter(cfg)
    raise ValueError(f"Unknown graph source: {src}")
