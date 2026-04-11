from __future__ import annotations

import io
import zipfile
from pathlib import Path

from src.convert_impl import convert_text_file
from src.options import ConvertOptions


def build_artifact_zip_bytes(input_path: Path, options: ConvertOptions) -> bytes:
    """Run conversion with artifact layout into a temp dir; return ZIP bytes (document.md only)."""
    import tempfile

    opts = options.with_overrides(artifact_layout=True)
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "artifact"
        convert_text_file(input_path, out, opts)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            doc = out / "document.md"
            if doc.is_file():
                zf.write(doc, "document.md")
    return buf.getvalue()
