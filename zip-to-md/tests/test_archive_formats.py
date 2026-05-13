from __future__ import annotations

import io
import sys
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from md_generator.archive.convert_impl import convert_archive, convert_zip
from md_generator.archive.extractors import (
    ArchiveExtractionError,
    MissingArchiveDependencyError,
    UnsupportedArchiveError,
    extract_archive,
    safe_member_path,
)
from md_generator.archive.options import ConvertOptions


def _write_tar(path: Path, members: dict[str, bytes], *, mode: str = "w:gz") -> None:
    with tarfile.open(path, mode) as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_convert_tar_gz_extracts_members(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.tar.gz"
    _write_tar(archive, {"notes/hello.txt": b"tar hello\n", "data/readme.md": b"# Tar\n"})
    out = tmp_path / "out"
    convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    text = (out / "document.md").read_text(encoding="utf-8")
    assert "# Archive Content Documentation (tar)" in text
    assert (out / "assets" / "files" / "notes" / "hello.txt").read_text(encoding="utf-8") == "tar hello\n"
    assert "tar hello" in text


def test_convert_tar_plain(tmp_path: Path) -> None:
    archive = tmp_path / "plain.tar"
    _write_tar(archive, {"only.txt": b"plain\n"}, mode="w")
    out = tmp_path / "plain_out"
    convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert (out / "assets" / "files" / "only.txt").is_file()


def test_convert_tar_bz2(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.tar.bz2"
    _write_tar(archive, {"bz.txt": b"bzip\n"}, mode="w:bz2")
    out = tmp_path / "bz_out"
    convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert (out / "assets" / "files" / "bz.txt").read_text(encoding="utf-8") == "bzip\n"


def test_nested_tar_expansion(tmp_path: Path) -> None:
    inner = io.BytesIO()
    with tarfile.open(fileobj=inner, mode="w:gz") as tf:
        data = b"deep tar\n"
        info = tarfile.TarInfo(name="deep/note.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    inner_bytes = inner.getvalue()

    outer = tmp_path / "outer.tar.gz"
    with tarfile.open(outer, "w:gz") as tf:
        info = tarfile.TarInfo(name="nested/inner.tar.gz")
        info.size = len(inner_bytes)
        tf.addfile(info, io.BytesIO(inner_bytes))
        top = b"top\n"
        top_info = tarfile.TarInfo(name="top.txt")
        top_info.size = len(top)
        tf.addfile(top_info, io.BytesIO(top))

    out = tmp_path / "nested_out"
    convert_archive(outer, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    deep = out / "assets" / "files" / "nested" / "inner_unzipped" / "deep" / "note.txt"
    assert deep.is_file()
    assert deep.read_text(encoding="utf-8") == "deep tar\n"


def test_convert_zip_alias_still_works(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("alias.txt", "alias ok\n")
    archive = tmp_path / "alias.zip"
    archive.write_bytes(buf.getvalue())
    out = tmp_path / "alias_out"
    convert_zip(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert "alias ok" in (out / "document.md").read_text(encoding="utf-8")


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    bad = tmp_path / "notes.txt"
    bad.write_text("not an archive\n", encoding="utf-8")
    with pytest.raises(ValueError, match="supported archive"):
        convert_archive(bad, tmp_path / "out", ConvertOptions())


def test_tar_skips_unsafe_member_paths(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        data = b"secret\n"
        info = tarfile.TarInfo(name="../../escape.txt")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    out = tmp_path / "unsafe_out"
    convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert not (out / "assets" / "files" / "escape.txt").exists()
    assert safe_member_path(out / "assets" / "files", "../../escape.txt", out / "assets" / "files") is None


def test_extract_archive_rejects_unknown_format(tmp_path: Path) -> None:
    bad = tmp_path / "data.bin"
    bad.write_bytes(b"not archive")
    with pytest.raises(UnsupportedArchiveError):
        extract_archive(bad, tmp_path / "dest", tmp_path / "dest", verbose=False)


@pytest.mark.parametrize("fmt", ["7z", "rar"])
def test_missing_optional_dependency_message(tmp_path: Path, fmt: str) -> None:
    archive = tmp_path / f"sample.{fmt}"
    archive.write_bytes(b"stub")
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(MissingArchiveDependencyError, match="archive-formats"):
        extract_archive(archive, dest, dest, verbose=False)


def test_convert_7z_when_py7zr_available(tmp_path: Path) -> None:
    pytest.importorskip("py7zr")
    import py7zr

    archive = tmp_path / "bundle.7z"
    with py7zr.SevenZipFile(archive, "w") as zf:
        zf.writestr("seven.txt", "seven ok\n")
    out = tmp_path / "seven_out"
    convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert (out / "assets" / "files" / "seven.txt").read_text(encoding="utf-8") == "seven ok\n"


def test_convert_rar_with_patool_mock(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.rar"
    archive.write_bytes(b"stub-rar")

    def fake_extract(archive_path: str, outdir: str, verbosity: int = -1) -> None:
        root = Path(outdir)
        (root / "nested").mkdir(parents=True, exist_ok=True)
        (root / "nested" / "mock.txt").write_text("rar ok\n", encoding="utf-8")

    import types

    fake_patool = types.ModuleType("patoolib")
    fake_patool.extract_archive = fake_extract
    with patch.dict(sys.modules, {"patoolib": fake_patool}):
        out = tmp_path / "rar_out"
        convert_archive(archive, out, ConvertOptions(enable_office=False, use_image_to_md=False))
    assert (out / "assets" / "files" / "nested" / "mock.txt").read_text(encoding="utf-8") == "rar ok\n"


def test_invalid_zip_raises_extraction_error(tmp_path: Path) -> None:
    bad = tmp_path / "broken.zip"
    bad.write_bytes(b"not a zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(ArchiveExtractionError):
        extract_archive(bad, dest, dest, verbose=False)
