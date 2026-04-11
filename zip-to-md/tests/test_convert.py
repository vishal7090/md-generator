from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from src.convert_impl import convert_zip
from src.options import ConvertOptions


def _build_sample_zip(buf: io.BytesIO) -> None:
    zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    zf.writestr("notes/hello.txt", "Line one\n\nLine two\n")
    zf.writestr("readme.md", "# Title\n\nBody.\n")
    zf.writestr("data/table.csv", "a,b\n1,2\n")
    zf.writestr("data/config.json", '{"x": 1}')
    zf.writestr("__MACOSX/._junk", "binary")
    zf.writestr("folder/.DS_Store", "junk")
    zf.writestr("Thumbs.db", "junk")
    png_minimal = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    zf.writestr("img/pixel.png", png_minimal)
    zf.writestr("src/hi.py", "print('hi')\n")
    zf.close()


def test_convert_zip_artifact_skips_junk_and_indexes(tmp_path: Path) -> None:
    buf = io.BytesIO()
    _build_sample_zip(buf)
    zpath = tmp_path / "in.zip"
    zpath.write_bytes(buf.getvalue())

    out = tmp_path / "out"
    convert_zip(
        zpath,
        out,
        ConvertOptions(enable_office=False),
    )

    doc = out / "document.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "# ZIP Content Documentation" in text
    assert "## File Index" in text
    assert "`notes/hello.txt`" in text
    assert "`readme.md`" in text
    assert "`data/table.csv`" in text
    assert "`img/pixel.png`" in text
    assert "__MACOSX" not in text
    assert ".DS_Store" not in text
    assert "Thumbs.db" not in text

    assert (out / "assets" / "files" / "notes" / "hello.txt").is_file()
    assert not (out / "assets" / "files" / "__MACOSX").exists()

    assert "### /notes/hello.txt" in text
    assert "Line one" in text
    assert "| a | b |" in text
    assert "```json" in text
    assert "```python" in text
    imgs = list((out / "assets" / "images").glob("*.png"))
    assert len(imgs) >= 1
    assert "assets/images/" in text.replace("\\", "/")


def test_max_bytes_truncates(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("big.txt", "x" * 20_000)
    zpath = tmp_path / "big.zip"
    zpath.write_bytes(buf.getvalue())
    out = tmp_path / "out2"
    convert_zip(zpath, out, ConvertOptions(enable_office=False, max_bytes=100))
    text = (out / "document.md").read_text(encoding="utf-8")
    assert "Truncated" in text


@pytest.mark.integration
def test_office_subprocess_when_siblings_present(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    if not (repo / "word-to-md" / "converter.py").is_file():
        pytest.skip("monorepo siblings not present")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stub.txt", "ok")
    zpath = tmp_path / "only_txt.zip"
    zpath.write_bytes(buf.getvalue())
    out = tmp_path / "off"
    convert_zip(zpath, out, ConvertOptions(enable_office=True, repo_root=str(repo), verbose=False))
    assert "ok" in (out / "document.md").read_text(encoding="utf-8")
