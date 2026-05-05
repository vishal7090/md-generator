"""Optional MCP tools (requires ``mdengine[mcp]``). Celery/Redis replacement: document only — jobs use SQLite."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.codeflow.api.schemas import AnalyzeOptions, merge_upload_options_json, options_to_scan_config
from md_generator.codeflow.core.extractor import build_output_zip


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "codeflow-to-md",
        instructions="Analyze Python/Java source archives into execution-flow Markdown and graphs.",
        streamable_http_path=path,
    )

    @mcp.tool()
    def codeflow_analyze_zip_base64(
        zip_base64: str,
        formats: str = "md,mermaid,json",
        options_json: str | None = None,
    ) -> str:
        """Analyze a ZIP of sources; return base64-encoded output ZIP.

        When ``options_json`` is set, it is parsed like ``POST /analyze`` (same shape as
        :class:`AnalyzeOptions`): depth, languages, ``enable_embeddings``, ``semantic_search``,
        ``emit_html_unified``, ``cluster_mode``, etc. The ``formats`` argument is ignored in
        that case unless the JSON also includes a ``formats`` field.

        When ``options_json`` is omitted, ``formats`` alone selects output types (legacy behavior).
        """
        import base64
        import tempfile
        import zipfile

        raw = base64.b64decode(zip_base64)
        td = Path(tempfile.mkdtemp(prefix="codeflow-mcp-"))
        src = td / "src"
        src.mkdir(parents=True, exist_ok=True)
        zpath = td / "in.zip"
        zpath.write_bytes(raw)

        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(src)

        if options_json and str(options_json).strip():
            opts = merge_upload_options_json(options_json)
        else:
            opts = AnalyzeOptions(formats=formats)
        cfg = options_to_scan_config(src, "out", opts)
        data = build_output_zip(cfg, workspace_root=src)
        return base64.b64encode(data).decode("ascii")

    sub = mcp.streamable_http_app()
    return mcp, sub
