from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from src.convert_impl import convert_text_file
from src.options import ConvertOptions

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_txt() -> Path:
    p = FIXTURES / "sample.txt"
    assert p.is_file()
    return p


@pytest.fixture
def sample_json() -> Path:
    p = FIXTURES / "sample.json"
    assert p.is_file()
    return p


@pytest.fixture
def sample_xml() -> Path:
    p = FIXTURES / "sample.xml"
    assert p.is_file()
    return p


def test_txt_classic(sample_txt: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    convert_text_file(
        sample_txt,
        out,
        ConvertOptions(artifact_layout=False, include_source_block=True),
    )
    text = out.read_text(encoding="utf-8")
    assert "Introduction" in text or "# Introduction" in text
    assert "| Name |" in text and "Vishal" in text
    assert "- First bullet" in text


def test_json_classic_with_source(sample_json: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    raw = sample_json.read_text(encoding="utf-8")
    convert_text_file(
        sample_json,
        out,
        ConvertOptions(artifact_layout=False, include_source_block=True),
    )
    text = out.read_text(encoding="utf-8")
    assert "## User" in text
    assert "**Name:**" in text or "Name" in text
    assert "Java" in text and "Spring" in text
    assert "```json" in text
    assert raw.strip() in text or '"user"' in text


def test_json_no_source_block(sample_json: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    convert_text_file(
        sample_json,
        out,
        ConvertOptions(artifact_layout=False, include_source_block=False),
    )
    text = out.read_text(encoding="utf-8")
    assert "```json" not in text


def test_xml_with_source(sample_xml: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    raw = sample_xml.read_text(encoding="utf-8")
    convert_text_file(
        sample_xml,
        out,
        ConvertOptions(artifact_layout=False, include_source_block=True),
    )
    text = out.read_text(encoding="utf-8")
    assert "## User" in text
    assert "Vishal" in text
    assert "```xml" in text
    assert "user" in raw.lower()


def test_artifact_layout(sample_json: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "artifact"
    convert_text_file(
        sample_json,
        out_dir,
        ConvertOptions(artifact_layout=True, include_source_block=True),
    )
    doc = out_dir / "document.md"
    assert doc.is_file()
    assert "## User" in doc.read_text(encoding="utf-8")


def test_artifact_zip_bytes(sample_json: Path) -> None:
    from api.convert_runner import build_artifact_zip_bytes

    zbytes = build_artifact_zip_bytes(
        sample_json,
        ConvertOptions(artifact_layout=True, include_source_block=True),
    )

    with zipfile.ZipFile(io.BytesIO(zbytes), "r") as zf:
        names = zf.namelist()
    assert "document.md" in names
