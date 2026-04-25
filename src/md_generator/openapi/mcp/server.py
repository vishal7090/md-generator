from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig
from md_generator.openapi.core.zip_export import build_markdown_zip_bytes
from md_generator.openapi.writers.markdown_writer import format_readme


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "openapi-to-md",
        instructions="Convert OpenAPI (YAML/JSON) to deterministic Markdown, Mermaid, and graphs.",
        streamable_http_path=path,
    )

    @mcp.tool()
    def api_validate_openapi_yaml(spec_yaml: str) -> str:
        import yaml

        data = yaml.safe_load(spec_yaml)
        if not isinstance(data, dict):
            return "error: root must be mapping"
        if not (data.get("openapi") or data.get("swagger")):
            return "error: missing openapi/swagger version"
        return "ok"

    @mcp.tool()
    def api_generate_readme_markdown(spec_yaml: str) -> str:
        import yaml

        data = yaml.safe_load(spec_yaml)
        if not isinstance(data, dict):
            return ""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(spec_yaml)
            p = Path(tmp.name)
        try:
            cfg = ApiRunConfig(file=p, output_path=Path("."), formats=("md", "mermaid")).normalized()
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "out"
                cfg2 = cfg.with_output(out)
                meta = extract_to_markdown(cfg2)
                return format_readme(meta)
        finally:
            p.unlink(missing_ok=True)

    @mcp.tool()
    def api_run_sync_zip_base64(spec_yaml: str) -> str:
        import yaml

        if not isinstance(yaml.safe_load(spec_yaml), dict):
            raise ValueError("spec_yaml must be YAML mapping")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(spec_yaml)
            p = Path(tmp.name)
        try:
            cfg = ApiRunConfig(file=p, output_path=Path("."), formats=("md", "mermaid", "html")).normalized()
            data = build_markdown_zip_bytes(cfg)
            return base64.b64encode(data).decode("ascii")
        finally:
            p.unlink(missing_ok=True)

    sub = mcp.streamable_http_app()
    return mcp, sub
