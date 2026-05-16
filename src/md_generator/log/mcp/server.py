from __future__ import annotations

import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.log.api.schemas import LogToMdRunBody
from md_generator.log.core.zip_export import build_log_markdown_zip_bytes
from md_generator.log.service.service import run_log_pipeline


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "log-to-md",
        instructions="Normalize log files to AI-oriented Markdown (summary, incidents, optional clusters).",
        streamable_http_path=path,
    )

    @mcp.tool()
    def log_validate_config(config_json: str) -> str:
        LogToMdRunBody.model_validate(json.loads(config_json))
        return "ok"

    @mcp.tool()
    def log_list_presets() -> str:
        from md_generator.log.config.preset_loader import list_preset_names

        return json.dumps({"presets": list_preset_names()}, indent=2)

    @mcp.tool()
    def log_parser_from_regex(line_regex: str, sample_text: str = "") -> str:
        """Build parser config JSON using a custom line_regex; optionally auto-score against sample."""
        from md_generator.log.parser.regex_parser import try_structured_match
        from md_generator.log.utils.regex import compile_optional

        pat = compile_optional(line_regex)
        if pat is None:
            return json.dumps({"error": "invalid regex"})
        matches = 0
        if sample_text.strip():
            for line in sample_text.splitlines()[:200]:
                if line.strip() and try_structured_match(line, pat):
                    matches += 1
        return json.dumps(
            {
                "parser": {
                    "preset": "generic",
                    "line_regex": line_regex,
                    "auto_detect": False,
                },
                "sample_matches": matches,
            },
            indent=2,
        )

    @mcp.tool()
    def log_run_sync_zip_base64(config_json: str) -> str:
        body = LogToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_log_run_config()
        data = build_log_markdown_zip_bytes(cfg)
        return base64.b64encode(data).decode("ascii")

    @mcp.tool()
    def log_run_sync_write_zip(config_json: str, output_zip_path: str) -> str:
        body = LogToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_log_run_config()
        data = build_log_markdown_zip_bytes(cfg)
        out = Path(output_zip_path).expanduser().resolve()
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def log_preview_readme_markdown(config_json: str) -> str:
        body = LogToMdRunBody.model_validate(json.loads(config_json))
        cfg = body.to_log_run_config()
        out = run_log_pipeline(cfg)
        p = out / "README.md"
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    sub = mcp.streamable_http_app()
    return mcp, sub
