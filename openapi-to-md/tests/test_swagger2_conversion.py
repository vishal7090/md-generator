from __future__ import annotations

from pathlib import Path

from md_generator.openapi.converters.swagger2_to_openapi3 import convert_swagger2_to_openapi3, is_swagger2_document
from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "swagger2_minimal.yaml"


def test_is_swagger2() -> None:
    import yaml

    doc = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    assert is_swagger2_document(doc) is True


def test_convert_produces_openapi3_with_servers_and_paths() -> None:
    import yaml

    doc = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    out = convert_swagger2_to_openapi3(doc)
    assert out["openapi"] == "3.0.3"
    assert out["paths"]["/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert "components" in out and "User" in out["components"]["schemas"]
    assert out["servers"] and "api.example.com" in out["servers"][0]["url"]


def test_extract_end_to_end_swagger2_fixture(tmp_path: Path) -> None:
    cfg = ApiRunConfig(file=_FIXTURE, output_path=tmp_path, formats=("md",))
    meta = extract_to_markdown(cfg)
    assert meta.title == "Sample API"
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "endpoints" / "get__users.md").is_file()
