"""Zip artifact directory (document.md + assets/)."""

from __future__ import annotations

import zipfile
from pathlib import Path


def zip_artifact_dir(bundle_root: Path, zip_path: Path) -> None:
    bundle_root = Path(bundle_root).resolve()
    zip_path = Path(zip_path).resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_root.rglob("*"):
            if path.is_file():
                arc = path.relative_to(bundle_root)
                zf.write(path, arc.as_posix())
