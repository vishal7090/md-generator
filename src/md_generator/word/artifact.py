from __future__ import annotations

import io
import zipfile
from pathlib import Path


ARTIFACT_MD_NAME = "document.md"
ARTIFACT_LOG_NAME = "conversion_log.txt"
ARTIFACT_IMAGES_DIR = "images"


def zip_artifact_directory(artifact_dir: Path) -> bytes:
    """Zip document.md, images/, conversion_log.txt under artifact_dir."""
    buf = io.BytesIO()
    md_path = artifact_dir / ARTIFACT_MD_NAME
    log_path = artifact_dir / ARTIFACT_LOG_NAME
    images_dir = artifact_dir / ARTIFACT_IMAGES_DIR

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if md_path.is_file():
            zf.write(md_path, ARTIFACT_MD_NAME)
        if log_path.is_file():
            zf.write(log_path, ARTIFACT_LOG_NAME)
        if images_dir.is_dir():
            for f in sorted(images_dir.rglob("*")):
                if f.is_file():
                    arc = f.relative_to(artifact_dir).as_posix()
                    zf.write(f, arc)
    return buf.getvalue()
