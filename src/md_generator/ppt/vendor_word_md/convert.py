from __future__ import annotations

import io
import os
from pathlib import Path

import mammoth
from markdownify import markdownify as html_to_md


def docx_to_markdown_bundle(
    docx_bytes: bytes,
    *,
    media_dir: Path,
    md_output_path: Path,
) -> tuple[str, list[Path]]:
    """
    Convert .docx bytes to Markdown; write images under media_dir.
    Returns (markdown, list of written image paths).
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    md_output_path = md_output_path.resolve()
    base_parent = md_output_path.parent

    def convert_image(image):
        ext = image.content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        name = f"img_{len(written)+1}.{ext}"
        path = media_dir / name
        with image.open() as f:
            path.write_bytes(f.read())
        written.append(path)
        rel = os.path.relpath(path.resolve(), base_parent).replace("\\", "/")
        return {"src": rel}

    result = mammoth.convert_to_html(
        io.BytesIO(docx_bytes),
        convert_image=mammoth.images.img_element(convert_image),
    )
    md = html_to_md(result.value, heading_style="ATX").strip()
    return md, written
