from __future__ import annotations

import shutil
from pathlib import Path

from md_generator.word.artifact import ARTIFACT_IMAGES_DIR, ARTIFACT_LOG_NAME, ARTIFACT_MD_NAME

STAGING_DOCX_NAME = "upload.docx"
from md_generator.word.converter import convert_docx_to_markdown


def convert_upload_to_artifact_dir(
    docx_path: Path,
    workdir: Path,
    *,
    page_break_as_hr: bool,
) -> None:
    """Run conversion into workdir (document.md, images/, conversion_log.txt)."""
    workdir.mkdir(parents=True, exist_ok=True)
    md_out = workdir / ARTIFACT_MD_NAME
    images_dir = workdir / ARTIFACT_IMAGES_DIR
    log_path = workdir / ARTIFACT_LOG_NAME
    convert_docx_to_markdown(
        docx_path,
        md_out,
        images_dir=images_dir,
        page_break_as_hr=page_break_as_hr,
        conversion_log_path=log_path,
    )


def stage_docx_bytes(dest: Path, data: bytes) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def copy_docx_to(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest
