from __future__ import annotations

import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.db.api.schemas import DbToMdRunBody
from md_generator.db.core.zip_export import build_markdown_zip_bytes


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "db-to-md",
        instructions="Export database metadata to deterministic Markdown (PostgreSQL, MySQL, Oracle, MongoDB).",
        streamable_http_path=path,
    )

    @mcp.tool()
    def db_validate_config(config_json: str) -> str:
        """Parse JSON config (same shape as POST /db-to-md/run body) and return validation message or 'ok'."""
        data = json.loads(config_json)
        DbToMdRunBody.model_validate(data)
        return "ok"

    @mcp.tool()
    def db_run_sync_zip_base64(config_json: str) -> str:
        """Run synchronous export; return base64 of ZIP (use only for small schemas)."""
        body = DbToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        data = build_markdown_zip_bytes(cfg)
        return base64.b64encode(data).decode("ascii")

    @mcp.tool()
    def db_run_sync_write_zip(config_json: str, output_zip_path: str) -> str:
        """Run synchronous export and write ZIP bytes to output_zip_path on server."""
        body = DbToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        data = build_markdown_zip_bytes(cfg)
        out = Path(output_zip_path).expanduser().resolve()
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def db_preview_readme_markdown(config_json: str) -> str:
        """Run export to a temp dir and return README.md contents only."""
        body = DbToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_run_config()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "out"
            from md_generator.db.core.extractor import extract_to_markdown

            extract_to_markdown(cfg.with_output(root))
            p = root / "README.md"
            return p.read_text(encoding="utf-8") if p.is_file() else ""

    sub = mcp.streamable_http_app()
    return mcp, sub
