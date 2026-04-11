from __future__ import annotations

import sys
from pathlib import Path

# Ensure package root on path when pytest collects from anywhere
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from md_generator.word.converter import convert_docx_to_markdown
from md_generator.word.artifact import ARTIFACT_LOG_NAME, ARTIFACT_MD_NAME


def test_convert_minimal_docx(sample_docx: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    log = tmp_path / ARTIFACT_LOG_NAME
    res = convert_docx_to_markdown(
        sample_docx,
        out,
        conversion_log_path=log,
        page_break_as_hr=True,
    )
    assert res.output_md == out
    text = out.read_text(encoding="utf-8")
    assert "HelloWordToMd" in text
    assert log.is_file()
    assert res.images_dir.is_dir()


def test_convert_writes_document_style_artifact_layout(tmp_path: Path, sample_docx: Path) -> None:
    work = tmp_path / "artifact"
    work.mkdir()
    md = work / ARTIFACT_MD_NAME
    images = work / "images"
    log = work / ARTIFACT_LOG_NAME
    convert_docx_to_markdown(
        sample_docx,
        md,
        images_dir=images,
        conversion_log_path=log,
    )
    assert md.read_text(encoding="utf-8")
    assert log.is_file()
