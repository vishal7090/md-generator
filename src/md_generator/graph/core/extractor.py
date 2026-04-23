from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from md_generator.graph.adapters.factory import create_adapter
from md_generator.graph.core.graph_builder import normalize_metadata
from md_generator.graph.core.markdown_writer import write_markdown_tree
from md_generator.graph.core.models import GraphMetadata
from md_generator.graph.core.run_config import GraphRunConfig
from md_generator.graph.core.viz import write_graph_mermaid, write_graph_viz

logger = logging.getLogger(__name__)


def _emit(on_progress: Callable[[int, str], None] | None, pct: int, cur: str) -> None:
    if on_progress:
        on_progress(pct, cur)


def extract_to_markdown(
    cfg: GraphRunConfig,
    *,
    on_progress: Callable[[int, str], None] | None = None,
    on_file: Callable[[Path], None] | None = None,
) -> GraphMetadata:
    cfg = cfg.normalized()
    adapter = create_adapter(cfg)
    _emit(on_progress, 0, "connect")
    adapter.validate_connection()
    adapter.connect()
    try:
        _emit(on_progress, 5, "graph_extraction_started")
        if cfg.source == "neo4j":
            from md_generator.graph.adapters.neo4j_adapter import Neo4jAdapter

            assert isinstance(adapter, Neo4jAdapter)
            meta = adapter.extract_bounded(cfg)
        else:
            nodes = adapter.get_nodes()
            rels = adapter.get_relationships()
            full = GraphMetadata(nodes=tuple(nodes), relationships=tuple(rels))
            meta = normalize_metadata(
                full,
                start_node=cfg.start_node,
                depth=cfg.depth,
                max_nodes=cfg.max_nodes,
                max_edges=cfg.max_edges,
            )
        _emit(on_progress, 40, "nodes_processed")
        _emit(on_progress, 50, "relationships_processed")

        out = Path(cfg.output_path)
        out.mkdir(parents=True, exist_ok=True)

        pct = [70]

        def _on_file(p: Path) -> None:
            if on_file:
                on_file(p)
            pct[0] = min(95, pct[0] + 1)
            _emit(on_progress, pct[0], "file_generated")

        include_viz = False
        if cfg.viz.enabled:
            _emit(on_progress, 60, "viz")
            include_viz = write_graph_viz(meta, out, formats=cfg.viz.formats)

        mermaid_body: str | None = None
        if cfg.viz.mermaid:
            _emit(on_progress, 62, "mermaid")
            mermaid_body = write_graph_mermaid(meta, out)
            mp = out / "graph" / "graph.mmd"
            if mp.is_file():
                _on_file(mp)

        _emit(on_progress, 65, "write_markdown")
        write_markdown_tree(
            meta,
            out,
            combine_markdown=cfg.combine_markdown,
            mermaid_body=mermaid_body,
            include_viz_readme=include_viz,
            on_file=_on_file,
        )
        _emit(on_progress, 100, "graph_completed")
        return meta
    finally:
        try:
            adapter.close()
        except Exception:
            logger.exception("adapter close failed")
