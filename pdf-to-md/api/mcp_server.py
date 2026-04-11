"""Standalone MCP server (stdio or streamable-http)."""

from __future__ import annotations

import argparse
import base64
import re
import tempfile
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from api.settings import max_upload_mb
from api.zip_bundle import zip_artifact_dir
from src.pdf_extract import ConvertOptions, convert_pdf_to_artifact_dir

mcp = FastMCP("pdf-to-md")

_DATA_URL = re.compile(r"^data:[^;]*;base64,", re.IGNORECASE)


def _max_bytes() -> int:
    return max(1, max_upload_mb()) * 1024 * 1024


@mcp.tool()
def convert_pdf_to_artifact_zip(pdf_path: str) -> str:
    """Convert a local PDF file to an artifact ZIP (document.md + assets/). Returns path to artifact.zip on the server."""
    src = Path(pdf_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"PDF not found: {src}")
    if src.stat().st_size > _max_bytes():
        raise ValueError(f"PDF exceeds PDF_TO_MD_MAX_UPLOAD_MB ({max_upload_mb()} MB)")
    tmp = Path(tempfile.mkdtemp(prefix="pdf-to-md-mcp-"))
    try:
        bundle = tmp / "bundle"
        zip_path = tmp / "artifact.zip"
        opts = ConvertOptions()
        convert_pdf_to_artifact_dir(src, bundle, opts)
        zip_artifact_dir(bundle, zip_path)
        return str(zip_path)
    except Exception:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
        raise


@mcp.tool()
def convert_pdf_base64_to_artifact_zip(pdf_base64: str, filename: str = "upload.pdf") -> str:
    """Decode a base64 PDF (optional data:...;base64, prefix), convert to artifact ZIP. Returns path to artifact.zip."""
    s = pdf_base64.strip()
    s = _DATA_URL.sub("", s)
    raw = base64.b64decode(s, validate=False)
    if len(raw) > _max_bytes():
        raise ValueError(f"Decoded PDF exceeds PDF_TO_MD_MAX_UPLOAD_MB ({max_upload_mb()} MB)")
    tmp = Path(tempfile.mkdtemp(prefix="pdf-to-md-mcp-b64-"))
    try:
        pdf_path = tmp / Path(filename).name
        pdf_path.write_bytes(raw)
        bundle = tmp / "bundle"
        zip_path = tmp / f"artifact_{uuid.uuid4().hex}.zip"
        opts = ConvertOptions()
        convert_pdf_to_artifact_dir(pdf_path, bundle, opts)
        zip_artifact_dir(bundle, zip_path)
        return str(zip_path)
    except Exception:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
        raise


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
    )
    p.add_argument(
        "--mount-path",
        default=None,
        help="Optional SSE mount path (see MCP docs).",
    )
    args = p.parse_args()
    if args.transport == "sse":
        mcp.run(transport="sse", mount_path=args.mount_path)
    else:
        mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
