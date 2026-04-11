from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_classic(tmp_path: Path, minimal_pdf_path: Path) -> None:
    out_md = tmp_path / "out.md"
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "converter.py"), str(minimal_pdf_path), str(out_md)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    text = out_md.read_text(encoding="utf-8")
    assert "## Page 1" in text
    assert "## Page 2" in text
    assert "Fixture page one" in text
    img_dir = out_md.parent / "images"
    assert img_dir.is_dir()
    assert any(img_dir.glob("page_2_img_*"))


def test_cli_artifact_layout(tmp_path: Path, minimal_pdf_path: Path) -> None:
    bundle = tmp_path / "bundle"
    r = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "converter.py"),
            str(minimal_pdf_path),
            str(bundle),
            "--artifact-layout",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    doc = bundle / "document.md"
    assert doc.is_file()
    body = doc.read_text(encoding="utf-8")
    assert "## Page 1" in body
    imgs = bundle / "assets" / "images"
    assert imgs.is_dir()
    assert any(imgs.glob("page_2_img_*"))
