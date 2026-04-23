from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

ALLOWED_SOURCES = frozenset({"networkx", "neo4j"})
ALLOWED_NEO4J_ID_MODE = frozenset({"element_id", "internal_id"})


@dataclass
class VizConfig:
    enabled: bool = False
    """When True, run Graphviz ``dot`` on ``graph.dot`` (requires ``dot`` on PATH)."""
    mermaid: bool = True
    """When True (default), write ``graph/graph.mmd`` and embed Mermaid in README (no Graphviz required)."""
    formats: tuple[str, ...] = ("png", "svg")  # dot always written when enabled


@dataclass
class GraphRunConfig:
    source: str = "networkx"
    uri: str = ""
    user: str = ""
    password: str = ""
    graph_file: Path | None = None
    neo4j_id_mode: str = "element_id"
    neo4j_database: str | None = None
    neo4j_page_size: int = 500
    connection_timeout_s: float = 30.0
    depth: int = 0  # 0 = unlimited depth for BFS cap only by max_nodes/edges
    start_node: str | None = None
    max_nodes: int = 10_000
    max_edges: int = 50_000
    output_path: Path = field(default_factory=lambda: Path("docs"))
    split_files: bool = True  # legacy; layout is controlled by combine_markdown
    combine_markdown: bool = True  # nodes.md + relationship.md + merged graph_summary.md
    workers: int = 4
    viz: VizConfig = field(default_factory=VizConfig)

    def with_output(self, path: Path) -> GraphRunConfig:
        return replace(self, output_path=path)

    def normalized(self) -> GraphRunConfig:
        src = (self.source or "networkx").lower().strip()
        if src not in ALLOWED_SOURCES:
            src = "networkx"
        mode = (self.neo4j_id_mode or "element_id").lower().strip()
        if mode not in ALLOWED_NEO4J_ID_MODE:
            mode = "element_id"
        depth = max(0, int(self.depth))
        max_nodes = max(1, min(int(self.max_nodes), 1_000_000))
        max_edges = max(1, min(int(self.max_edges), 5_000_000))
        ps = max(1, min(int(self.neo4j_page_size), 10_000))
        workers = max(1, min(int(self.workers), 32))
        to_s = float(self.connection_timeout_s)
        if to_s <= 0:
            to_s = 30.0
        fmts = tuple(
            f.strip().lower()
            for f in (self.viz.formats if self.viz.formats else ("png", "svg"))
            if f.strip()
        )
        if not fmts:
            fmts = ("png", "svg")
        viz = VizConfig(enabled=bool(self.viz.enabled), mermaid=bool(self.viz.mermaid), formats=fmts)
        db = (str(self.neo4j_database).strip() or None) if self.neo4j_database else None
        return GraphRunConfig(
            source=src,
            uri=str(self.uri or ""),
            user=str(self.user or ""),
            password=str(self.password or ""),
            graph_file=self.graph_file,
            neo4j_id_mode=mode,
            neo4j_database=db,
            neo4j_page_size=ps,
            connection_timeout_s=to_s,
            depth=depth,
            start_node=(str(self.start_node).strip() or None) if self.start_node else None,
            max_nodes=max_nodes,
            max_edges=max_edges,
            output_path=Path(self.output_path),
            split_files=bool(self.split_files),
            combine_markdown=bool(self.combine_markdown),
            workers=workers,
            viz=viz,
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_graph_run_config(path: Path | None, overrides: dict[str, Any] | None = None) -> GraphRunConfig:
    raw: dict[str, Any] = {}
    if path is not None and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path is None:
        try:
            import importlib.resources as ir

            txt = ir.files("md_generator.graph.config").joinpath("default.yaml").read_text(encoding="utf-8")
            raw = yaml.safe_load(txt) or {}
        except Exception:
            raw = {}
    if overrides:
        raw = _deep_merge(raw, overrides)

    g = raw.get("graph") or {}
    out = raw.get("output") or {}
    exe = raw.get("execution") or {}
    viz_raw = raw.get("viz") or {}

    gf = g.get("graph_file") or g.get("path") or out.get("graph_file")
    graph_file = Path(str(gf)).expanduser() if gf else None

    return GraphRunConfig(
        source=str(g.get("source", "networkx")).lower(),
        uri=str(g.get("uri", "")),
        user=str(g.get("user", "")),
        password=str(g.get("password", "")),
        graph_file=graph_file,
        neo4j_id_mode=str(g.get("neo4j_id_mode", "element_id")),
        neo4j_database=g.get("database") or g.get("neo4j_database"),
        neo4j_page_size=int(g.get("neo4j_page_size", 500)),
        connection_timeout_s=float(g.get("connection_timeout_s", 30.0)),
        depth=int(g.get("depth", 0)),
        start_node=g.get("start_node"),
        max_nodes=int(g.get("max_nodes", 10_000)),
        max_edges=int(g.get("max_edges", 50_000)),
        output_path=Path(str(out.get("path", "./docs"))),
        split_files=bool(out.get("split_files", True)),
        combine_markdown=bool(out.get("combine_markdown", True)),
        workers=int(exe.get("workers", 4)),
        viz=VizConfig(
            enabled=bool(viz_raw.get("enabled", False)),
            mermaid=bool(viz_raw.get("mermaid", True)),
            formats=tuple(str(x) for x in (viz_raw.get("formats") or ["png", "svg"])),
        ),
    ).normalized()


def graph_config_to_jsonable(cfg: GraphRunConfig) -> dict[str, Any]:
    return {
        "source": cfg.source,
        "uri": cfg.uri,
        "user": cfg.user,
        "password": cfg.password,
        "graph_file": str(cfg.graph_file) if cfg.graph_file else None,
        "neo4j_id_mode": cfg.neo4j_id_mode,
        "neo4j_database": cfg.neo4j_database,
        "neo4j_page_size": cfg.neo4j_page_size,
        "connection_timeout_s": cfg.connection_timeout_s,
        "depth": cfg.depth,
        "start_node": cfg.start_node,
        "max_nodes": cfg.max_nodes,
        "max_edges": cfg.max_edges,
        "output_path": str(cfg.output_path),
        "split_files": cfg.split_files,
        "combine_markdown": cfg.combine_markdown,
        "workers": cfg.workers,
        "viz_enabled": cfg.viz.enabled,
        "viz_mermaid": cfg.viz.mermaid,
        "viz_formats": list(cfg.viz.formats),
    }
