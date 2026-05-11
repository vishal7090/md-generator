from __future__ import annotations

import io
import zipfile
from pathlib import Path

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown


def build_log_markdown_zip_bytes(cfg: LogRunConfig) -> bytes:
    import tempfile

    cfg = cfg.normalized()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "out"
        run_cfg = _with_output(cfg, root)
        extract_to_markdown(run_cfg)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    arc = p.relative_to(root).as_posix()
                    zf.write(p, arc)
        return buf.getvalue()


def _with_output(cfg: LogRunConfig, path: Path) -> LogRunConfig:
    from dataclasses import replace

    return replace(cfg, output=replace(cfg.output, path=str(path)))
