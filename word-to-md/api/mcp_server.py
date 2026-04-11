from __future__ import annotations

import argparse
import base64
import shutil
import tempfile
from pathlib import Path

from fastmcp import FastMCP

from api.convert_util import (
    STAGING_DOCX_NAME,
    convert_upload_to_artifact_dir,
    copy_docx_to,
)
from src.artifact import zip_artifact_directory
from src.settings import load_settings

mcp = FastMCP("word-to-md")


@mcp.tool
def convert_docx_to_artifact_zip(docx_path: str, page_break_as_hr: bool = True) -> dict[str, str]:
    """
    Convert a .docx file on the server filesystem to a ZIP artifact (base64-encoded).
    The ZIP contains document.md, images/, and conversion_log.txt.
    """
    src = Path(docx_path)
    if not src.is_file():
        raise FileNotFoundError(f"not a file: {docx_path}")
    settings = load_settings()
    workdir = Path(tempfile.mkdtemp(prefix="word-md-mcp-", dir=settings.temp_dir))
    try:
        copy_docx_to(src, workdir / STAGING_DOCX_NAME)
        convert_upload_to_artifact_dir(
            workdir / STAGING_DOCX_NAME,
            workdir,
            page_break_as_hr=page_break_as_hr,
        )
        z = zip_artifact_directory(workdir)
        return {
            "artifact_zip_base64": base64.standard_b64encode(z).decode("ascii"),
            "filename": "artifact.zip",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@mcp.tool
def convert_docx_base64_to_artifact_zip(
    docx_base64: str,
    page_break_as_hr: bool = True,
) -> dict[str, str]:
    """
    Convert a base64-encoded .docx to the same ZIP artifact (base64-encoded ZIP).
    """
    settings = load_settings()
    workdir = Path(tempfile.mkdtemp(prefix="word-md-mcp-", dir=settings.temp_dir))
    try:
        raw = base64.standard_b64decode(docx_base64)
        (workdir / STAGING_DOCX_NAME).write_bytes(raw)
        convert_upload_to_artifact_dir(
            workdir / STAGING_DOCX_NAME,
            workdir,
            page_break_as_hr=page_break_as_hr,
        )
        z = zip_artifact_directory(workdir)
        return {
            "artifact_zip_base64": base64.standard_b64encode(z).decode("ascii"),
            "filename": "artifact.zip",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="word-to-md MCP server")
    p.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "http", "sse", "streamable-http"),
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8002)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    mcp.run(
        transport=args.transport,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
