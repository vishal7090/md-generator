from __future__ import annotations

from pathlib import Path

from md_generator.log.core.run_config import load_run_config
from md_generator.log.core.extractor import extract_to_markdown

_UNICODE_LINES = """\
2024-01-15T10:00:00Z INFO Application started — café résumé
2024-01-15T10:00:01Z ERROR Database connection failed: データベース接続失敗
2024-01-15T10:00:02Z WARN Retrying connection 🔄
2024-01-15T10:00:03Z ERROR Database connection failed
2024-01-15T10:00:04Z INFO Приложение восстановлено ✓
"""


def test_unicode_log_fixture(tmp_path: Path) -> None:
    """UTF-8 log ingest must work without relying on a committed *.log fixture (gitignored by default)."""
    log = tmp_path / "app.log"
    log.write_text(_UNICODE_LINES, encoding="utf-8")
    out = tmp_path / "out"
    cfg = load_run_config(None, {"input": {"paths": [str(log)]}, "output": {"path": str(out)}})
    extract_to_markdown(cfg.normalized())
    assert (out / "run_metadata.json").is_file()
