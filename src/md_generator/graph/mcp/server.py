from __future__ import annotations

import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.graph.api.schemas import GraphToMdRunBody
from md_generator.graph.core.markdown_writer import format_node_markdown, format_relationship_markdown
from md_generator.graph.core.zip_export import build_markdown_zip_bytes
from md_generator.graph.core.extractor import extract_to_markdown


def _metadata_to_jsonable(meta: object) -> dict:
    from md_generator.graph.core.models import GraphMetadata

    assert isinstance(meta, GraphMetadata)
    return {
        "nodes": [
            {"id": n.id, "labels": list(n.labels), "properties": dict(n.properties)} for n in sorted(meta.nodes, key=lambda x: x.id)
        ],
        "relationships": [
            {
                "id": r.id,
                "type": r.type,
                "start_node": r.start_node,
                "end_node": r.end_node,
                "properties": dict(r.properties),
            }
            for r in sorted(meta.relationships, key=lambda x: (x.type, x.id, x.start_node, x.end_node))
        ],
    }


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "graph-to-md",
        instructions="Export graph data (NetworkX, Neo4j) to deterministic Markdown.",
        streamable_http_path=path,
    )

    @mcp.tool()
    def graph_validate_config(config_json: str) -> str:
        data = json.loads(config_json)
        GraphToMdRunBody.model_validate(data)
        return "ok"

    @mcp.tool()
    def graph_run_sync_zip_base64(config_json: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        data = build_markdown_zip_bytes(cfg)
        return base64.b64encode(data).decode("ascii")

    @mcp.tool()
    def graph_run_sync_write_zip(config_json: str, output_zip_path: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        data = build_markdown_zip_bytes(cfg)
        out = Path(output_zip_path).expanduser().resolve()
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def graph_preview_readme_markdown(config_json: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "out"
            extract_to_markdown(cfg.with_output(root))
            p = root / "README.md"
            return p.read_text(encoding="utf-8") if p.is_file() else ""

    @mcp.tool()
    def graph_metadata_json(config_json: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "out"
            meta = extract_to_markdown(cfg.with_output(root))
        return json.dumps(_metadata_to_jsonable(meta), indent=2, sort_keys=True)

    @mcp.tool()
    def graph_preview_node_markdown(config_json: str, node_id: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "out"
            meta = extract_to_markdown(cfg.with_output(root))
        for n in meta.nodes:
            if n.id == node_id:
                return format_node_markdown(n, meta)
        return ""

    @mcp.tool()
    def graph_preview_rel_markdown(config_json: str, relationship_id: str) -> str:
        body = GraphToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "out"
            meta = extract_to_markdown(cfg.with_output(root))
        for r in meta.relationships:
            if r.id == relationship_id:
                return format_relationship_markdown(r, meta)
        return ""

    sub = mcp.streamable_http_app()
    return mcp, sub
