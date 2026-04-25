from __future__ import annotations

import io
import zipfile
from pathlib import Path

from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig


def build_markdown_zip_bytes(cfg: ApiRunConfig) -> bytes:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "out"
        cfg_run = cfg.with_output(root)
        extract_to_markdown(cfg_run)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    arc = p.relative_to(root).as_posix()
                    zf.write(p, arc)
        return buf.getvalue()
