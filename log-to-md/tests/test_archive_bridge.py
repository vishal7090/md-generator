from __future__ import annotations

import zipfile
from pathlib import Path

from md_generator.log.ingestion.archive_bridge import iter_log_files_from_archive


def test_iter_log_files_from_zip(tmp_path: Path) -> None:
    zpath = tmp_path / "logs.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("nested/app.log", "2024-01-01 ERROR boom\n")
    found = list(iter_log_files_from_archive(zpath, cleanup=True))
    assert len(found) == 1
    assert found[0].name == "app.log"
