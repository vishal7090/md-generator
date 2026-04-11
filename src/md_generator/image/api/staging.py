"""Stage multipart uploads (single image or ZIP of images)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from md_generator.image.io_util import IMAGE_EXTENSIONS


def _has_image_extension(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS)


def stage_upload_bytes(work_root: Path, filename: str | None, data: bytes) -> Path:
    """
    Write upload under work_root and return a path suitable for convert_images_recursive:
    - .zip: extracted directory (flat or nested images allowed)
    - image extension: path to that file
    """
    if not data:
        raise ValueError("empty upload")

    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    raw_name = Path(filename or "upload").name
    lower = raw_name.lower()

    if lower.endswith(".zip"):
        zpath = work_root / raw_name
        zpath.write_bytes(data)
        dest = work_root / "unzipped"
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(dest)
        return dest

    if not _has_image_extension(raw_name):
        raise ValueError(
            f"unsupported file type {raw_name!r}; use an image ({', '.join(sorted(IMAGE_EXTENSIONS))}) or .zip"
        )

    img_path = work_root / raw_name
    img_path.write_bytes(data)
    return img_path
