from __future__ import annotations

from pathlib import Path

from md_generator.log.ingestion.archive_bridge import iter_log_files_from_archive


def test_iter_log_files_from_tar_gz() -> None:
    archive = Path(__file__).resolve().parent / "fixtures" / "archives" / "nested-logs.tar.gz"
    assert archive.is_file()
    found = list(iter_log_files_from_archive(archive, cleanup=True))
    names = {p.name for p in found}
    assert "api.log" in names
    assert "worker.log" in names
