from __future__ import annotations

import io
import zipfile
from pathlib import Path

from md_generator.ppt.convert_impl import convert_pptx
from md_generator.ppt.options import ConvertOptions


def build_artifact_zip_bytes(pptx_path: Path, options: ConvertOptions) -> bytes:
    """Run conversion with artifact layout into a temp dir; return ZIP bytes (document.md + assets/)."""
    import tempfile

    opts = options.with_overrides(artifact_layout=True)
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "artifact"
        convert_pptx(pptx_path, out, opts)
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
