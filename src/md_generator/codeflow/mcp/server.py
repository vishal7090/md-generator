"""Optional MCP tools (requires ``mdengine[mcp]``). Celery/Redis replacement: document only — jobs use SQLite."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.codeflow.core.extractor import build_output_zip
from md_generator.codeflow.core.run_config import ScanConfig


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "codeflow-to-md",
        instructions="Analyze Python/Java source archives into execution-flow Markdown and graphs.",
        streamable_http_path=path,
    )

    @mcp.tool()
    def codeflow_analyze_zip_base64(zip_base64: str, formats: str = "md,mermaid,json") -> str:
        import base64
        import tempfile

        raw = base64.b64decode(zip_base64)
        td = Path(tempfile.mkdtemp(prefix="codeflow-mcp-"))
        src = td / "src"
        src.mkdir(parents=True, exist_ok=True)
        zpath = td / "in.zip"
        zpath.write_bytes(raw)
        import zipfile

        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(src)
        fmts = tuple(x.strip() for x in formats.split(",") if x.strip())
        cfg = ScanConfig(project_root=src, output_path=td / "out", formats=fmts)
        data = build_output_zip(cfg, workspace_root=src)
        return base64.b64encode(data).decode("ascii")

    sub = mcp.streamable_http_app()
    return mcp, sub
