from __future__ import annotations

from pathlib import Path

import pytest

from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_openapi.yaml"


def test_extract_writes_endpoints_and_graphs(tmp_path: Path) -> None:
    cfg = ApiRunConfig(file=_FIXTURE, output_path=tmp_path, formats=("md", "mermaid", "html"))
    meta = extract_to_markdown(cfg)
    assert meta.title == "Minimal Pet API"
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "endpoints" / "get__pets.md").is_file()
    assert (tmp_path / "endpoints" / "post__pets.md").is_file()
    assert (tmp_path / "endpoints" / "get__pets_id.md").is_file()
    assert (tmp_path / "graphs" / "api_dependency.mmd").is_file()
    assert (tmp_path / "graphs" / "api_dependency.dot").is_file()
    assert (tmp_path / "schemas" / "Pet.md").is_file()
