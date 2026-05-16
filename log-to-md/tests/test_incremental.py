from __future__ import annotations

from pathlib import Path

from md_generator.log.incremental.checkpoint import Checkpoint, load_checkpoint, save_checkpoint
from md_generator.log.incremental.resume_reader import iter_new_lines


def test_checkpoint_resume(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text("line1\n", encoding="utf-8")
    ck_path = tmp_path / "ck.json"
    save_checkpoint(ck_path, Checkpoint(path=str(log), offset=0))
    log.write_text("line1\nline2\n", encoding="utf-8")
    cp = load_checkpoint(ck_path)
    lines = [text for _ln, text, _off in iter_new_lines(log, cp)]
    assert "line2" in lines
