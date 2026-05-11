from __future__ import annotations

from pathlib import Path

import pytest

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown


def test_extract_writes_readme_and_summary(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample.log"
    out = tmp_path / "out"
    cfg = LogRunConfig()
    from dataclasses import replace

    cfg = replace(
        cfg,
        input=replace(cfg.input, paths=[str(fixture)]),
        output=replace(cfg.output, path=str(out)),
        clustering=replace(cfg.clustering, enabled=False),
    ).normalized()
    extract_to_markdown(cfg)
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "Total records" in readme
    assert (out / "summary" / "levels.md").is_file()
    assert (out / "run_metadata.json").is_file()
    meta = (out / "run_metadata.json").read_text(encoding="utf-8")
    assert "log-to-md" in meta


@pytest.mark.integration
def test_clustering_when_sklearn_installed(tmp_path: Path) -> None:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        pytest.skip("scikit-learn not installed")
    fixture = Path(__file__).resolve().parent / "fixtures" / "sample.log"
    out = tmp_path / "cout"
    from dataclasses import replace

    cfg = LogRunConfig()
    cfg = replace(
        cfg,
        input=replace(cfg.input, paths=[str(fixture)]),
        output=replace(cfg.output, path=str(out), generate_clusters=True),
        clustering=replace(cfg.clustering, enabled=True, n_clusters=2),
    ).normalized()
    extract_to_markdown(cfg)
    assert any((out / "clusters").glob("cluster_*.md"))
