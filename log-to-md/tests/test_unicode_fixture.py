from __future__ import annotations

from pathlib import Path

from md_generator.log.core.run_config import load_run_config
from md_generator.log.core.extractor import extract_to_markdown


def test_unicode_log_fixture() -> None:
    root = Path(__file__).resolve().parent
    log = root / "fixtures" / "unicode" / "app.log"
    out = root / "_out_unicode"
    cfg = load_run_config(None, {"input": {"paths": [str(log)]}, "output": {"path": str(out)}})
    extract_to_markdown(cfg.normalized())
    assert (out / "run_metadata.json").is_file()
