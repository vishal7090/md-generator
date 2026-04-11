from __future__ import annotations

import io
import zipfile
from pathlib import Path

from src.convert_impl import convert_zip
from src.options import ConvertOptions


def build_artifact_zip_bytes(zip_path: Path, options: ConvertOptions) -> bytes:
    """Run conversion into a temp artifact dir; return ZIP bytes (document.md + assets/)."""
    import tempfile

    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "artifact"
        convert_zip(zip_path, out, options)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            doc = out / "document.md"
            if doc.is_file():
                zf.write(doc, "document.md")
            assets = out / "assets"
            if assets.is_dir():
                for p in sorted(assets.rglob("*")):
                    if p.is_file():
                        arc = Path("assets") / p.relative_to(assets)
                        zf.write(p, arc.as_posix())
    return buf.getvalue()
