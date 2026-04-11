from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from api.convert_runner import build_artifact_zip_bytes
from api.settings import ApiSettings
from src.options import ConvertOptions


def _decode_base64_payload(data: str) -> bytes:
    s = data.strip()
    if s.startswith("data:"):
        parts = s.split(",", 1)
        if len(parts) == 2:
            s = parts[1]
    return base64.b64decode(s, validate=False)


def build_mcp_stack(*, mount_under_fastapi: bool = False) -> tuple[FastMCP, object]:
    path = "/" if mount_under_fastapi else "/mcp"
    mcp = FastMCP(
        "txt-json-xml-to-md",
        instructions="Convert .txt, .json, or .xml files to Markdown inside a ZIP (document.md).",
        streamable_http_path=path,
    )
    settings = ApiSettings()

    @mcp.tool()
    def convert_text_file_to_artifact_zip(file_path: str) -> str:
        """Convert a local .txt, .json, or .xml path on the server to a temporary artifact.zip path."""
        src = Path(file_path).expanduser().resolve()
        suf = src.suffix.lower()
        if not src.is_file() or suf not in (".txt", ".json", ".xml"):
            raise ValueError("file_path must be an existing .txt, .json, or .xml file")
        opts = ConvertOptions(artifact_layout=True)
        data = build_artifact_zip_bytes(src, opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="txjxml-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    @mcp.tool()
    def convert_text_base64_to_artifact_zip(
        file_base64: str,
        filename: str = "upload.txt",
    ) -> str:
        """Decode base64 (optional data:...;base64, prefix) and write artifact.zip path."""
        raw = _decode_base64_payload(file_base64)
        max_b = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_b:
            raise ValueError(f"Decoded file exceeds TXT_JSON_XML_TO_MD_MAX_UPLOAD_MB ({settings.max_upload_mb})")
        safe = re.sub(r"[^\w.\-]+", "_", filename) or "upload.txt"
        lower = safe.lower()
        if not lower.endswith((".txt", ".json", ".xml")):
            safe += ".txt"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / safe
            p.write_bytes(raw)
            opts = ConvertOptions(artifact_layout=True)
            data = build_artifact_zip_bytes(p, opts)
        fd, name = tempfile.mkstemp(suffix=".zip", prefix="txjxml-artifact-")
        import os

        os.close(fd)
        out = Path(name)
        out.write_bytes(data)
        return str(out)

    sub = mcp.streamable_http_app()
    return mcp, sub
