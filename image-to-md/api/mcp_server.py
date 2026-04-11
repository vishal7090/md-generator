"""Standalone MCP server (stdio or streamable-http); mounted under FastAPI at /mcp."""

from __future__ import annotations

import argparse
import base64
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from mcp.server.fastmcp import FastMCP

from api.query_options import convert_options_from_query
from api.settings import max_upload_mb
from api.zip_bundle import zip_artifact_dir
from src.convert_impl import convert_images_recursive
from src.io_util import is_image_path, iter_image_paths_recursive

mcp = FastMCP("image-to-md")

_DATA_URL = re.compile(r"^data:[^;]*;base64,", re.IGNORECASE)


def _max_bytes() -> int:
    return max(1, max_upload_mb()) * 1024 * 1024


def _opts(
    engines: str,
    strategy: str,
    title: str,
    lang: str,
    paddle_lang: str,
    paddle_no_angle_cls: bool,
    easy_lang: str,
):
    if strategy not in ("compare", "best"):
        raise ValueError("strategy must be compare or best")
    return convert_options_from_query(
        engines=engines,
        strategy=strategy,
        title=title,
        lang=lang,
        paddle_lang=paddle_lang,
        paddle_no_angle_cls=paddle_no_angle_cls,
        easy_lang=easy_lang,
    )


def _image_count(staged: Path) -> int:
    if staged.is_file():
        return 1 if is_image_path(staged) else 0
    return len(iter_image_paths_recursive(staged))


@mcp.tool()
def convert_image_path_to_artifact_zip(
    image_path: str,
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> str:
    """Convert a local image file, directory of images, or extracted ZIP tree to artifact.zip (document.md). Returns path to artifact.zip on the server."""
    src = Path(image_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Path not found: {src}")
    if src.is_file() and not is_image_path(src) and not src.name.lower().endswith(".zip"):
        raise ValueError(f"Not an image or .zip: {src}")
    if src.is_file() and src.stat().st_size > _max_bytes():
        raise ValueError(f"File exceeds IMAGE_TO_MD_MAX_UPLOAD_MB ({max_upload_mb()} MB)")

    tmp = Path(tempfile.mkdtemp(prefix="image-to-md-mcp-"))
    try:
        staged = src
        if src.is_file() and src.name.lower().endswith(".zip"):
            dest = tmp / "unzipped"
            dest.mkdir(parents=True, exist_ok=True)
            import zipfile

            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(dest)
            staged = dest

        if _image_count(staged) == 0:
            raise ValueError("No supported images found under input path")

        opts = _opts(engines, strategy, title, lang, paddle_lang, paddle_no_angle_cls, easy_lang)
        bundle = tmp / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        zip_path = tmp / "artifact.zip"
        convert_images_recursive(staged, bundle / "document.md", opts)
        zip_artifact_dir(bundle, zip_path)
        return str(zip_path)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


@mcp.tool()
def convert_image_base64_to_artifact_zip(
    image_base64: str,
    filename: str = "upload.png",
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> str:
    """Decode base64 image or zip (optional data:...;base64, prefix), convert to artifact.zip. Returns path to artifact.zip."""
    s = image_base64.strip()
    s = _DATA_URL.sub("", s)
    raw = base64.b64decode(s, validate=False)
    if len(raw) > _max_bytes():
        raise ValueError(f"Decoded payload exceeds IMAGE_TO_MD_MAX_UPLOAD_MB ({max_upload_mb()} MB)")

    tmp = Path(tempfile.mkdtemp(prefix="image-to-md-mcp-b64-"))
    try:
        from api.staging import stage_upload_bytes

        staged = stage_upload_bytes(tmp / "stage", filename, raw)
        if _image_count(staged) == 0:
            raise ValueError("No supported images in upload")

        opts = _opts(engines, strategy, title, lang, paddle_lang, paddle_no_angle_cls, easy_lang)
        bundle = tmp / "bundle"
        bundle.mkdir(parents=True, exist_ok=True)
        zip_path = tmp / f"artifact_{uuid.uuid4().hex}.zip"
        convert_images_recursive(staged, bundle / "document.md", opts)
        zip_artifact_dir(bundle, zip_path)
        return str(zip_path)
    except Exception:
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
