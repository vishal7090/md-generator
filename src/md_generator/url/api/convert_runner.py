from __future__ import annotations

import io
import zipfile
from pathlib import Path

from md_generator.url.convert_impl import convert_url_job
from md_generator.url.options import ConvertOptions


def zip_directory(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                arc = p.relative_to(root)
                zf.write(p, arc.as_posix())
    return buf.getvalue()


def build_artifact_zip_bytes(
    *,
    url: str | None,
    urls: list[str] | None,
    options: ConvertOptions,
) -> bytes:
    """Run conversion into a temp dir; return ZIP bytes (document.md + assets/ + pages/ when applicable)."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "artifact"
        out.mkdir(parents=True, exist_ok=True)
        convert_url_job(url, urls, out, options)
        return zip_directory(out)
