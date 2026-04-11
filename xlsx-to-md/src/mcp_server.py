"""MCP server exposing xlsx-to-md conversion (optional dependency: mcp)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.convert_config import ConvertConfig
from src.converter_core import convert_excel_to_markdown

logger = logging.getLogger(__name__)


def build_mcp_server() -> FastMCP:
    mcp = FastMCP(
        "xlsx-to-md",
        instructions="Convert Excel .xlsx/.xlsm workbooks to GitHub-flavored Markdown.",
        streamable_http_path="/",
    )

    @mcp.tool()
    def convert_excel_to_markdown_paths(
        excel_path: str,
        output_dir: str,
        split_by_sheet: bool = False,
        config_json: str | None = None,
    ) -> str:
        """Convert a workbook on disk to Markdown under output_dir.

        config_json: optional JSON object with ConvertConfig fields (see README).
        """
        inp = Path(excel_path).expanduser().resolve()
        out = Path(output_dir).expanduser().resolve()
        cfg = ConvertConfig.from_dict(json.loads(config_json)) if config_json else ConvertConfig()
        if split_by_sheet:
            cfg = cfg.merged_with_overrides(split_by_sheet=True)
        logger.info("MCP convert: %s -> %s", inp, out)
        result = convert_excel_to_markdown(inp, out, config=cfg)
        lines = [
            f"paths_written: {[str(p) for p in result.paths_written]}",
            f"sheets_processed: {result.sheets_processed}",
        ]
        if result.warnings:
            lines.append("warnings: " + "; ".join(result.warnings))
        return "\n".join(lines)

    return mcp
