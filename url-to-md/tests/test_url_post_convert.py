from __future__ import annotations

import json
from pathlib import Path

import pytest

from md_generator.url.options import ConvertOptions
from md_generator.url.post_convert_assets import process_downloaded_files


def test_post_convert_skips_when_disabled(tmp_path: Path) -> None:
    root = tmp_path / "page"
    (root / "assets" / "files").mkdir(parents=True)
    (root / "assets" / "files" / "a.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    opts = ConvertOptions(
        artifact_layout=True,
        convert_downloaded_assets=False,
        convert_downloaded_images=False,
    )
    assert process_downloaded_files(root, opts) == ""


def test_post_convert_pdf_creates_extracted(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    root = tmp_path / "page"
    files = root / "assets" / "files"
    files.mkdir(parents=True)
    pdf_path = files / "hello.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Hello PDF")
    doc.save(pdf_path)
    doc.close()

    opts = ConvertOptions(artifact_layout=True, convert_downloaded_assets=True, verbose=False)
    appendix = process_downloaded_files(root, opts)
    log = json.loads((root / "assets" / "asset_convert_log.json").read_text(encoding="utf-8"))
    assert any(e.get("status") == "ok" for e in log.get("entries", []))
    assert "Downloaded files converted to Markdown" in appendix or "Hello PDF" in appendix
