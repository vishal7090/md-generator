from __future__ import annotations

from pathlib import Path

from md_generator.db.core.markdown_writer import format_run_readme
from md_generator.db.core.models import RunMetadata


def test_format_run_readme_toc_merge(tmp_path: Path) -> None:
    (tmp_path / "functions.md").write_text("# Fn\n\nbody\n", encoding="utf-8")
    meta = RunMetadata(
        db_type="postgres",
        uri_display="postgresql://x",
        schema="public",
        database=None,
        included_features=("functions",),
        limits={},
        readme_feature_merge="toc",
        combined_readme_paths=("functions.md",),
    )
    text = format_run_readme(meta, output_root=tmp_path)
    assert "## Combined documentation" in text
    assert "[`functions.md`](functions.md)" in text
    assert "aggregate each feature" in text


def test_format_run_readme_inline_merge(tmp_path: Path) -> None:
    (tmp_path / "views.md").write_text("# V1\n\nalpha\n", encoding="utf-8")
    meta = RunMetadata(
        db_type="postgres",
        uri_display="postgresql://x",
        schema="public",
        database=None,
        included_features=("views",),
        limits={},
        readme_feature_merge="inline",
        combined_readme_paths=("views.md",),
    )
    text = format_run_readme(meta, output_root=tmp_path)
    assert "## Combined documentation" in text
    assert "### Views (combined)" in text
    assert "alpha" in text


def test_ordered_paths_sorts_log() -> None:
    from md_generator.db.core.markdown_writer import ordered_combined_readme_paths

    assert ordered_combined_readme_paths(["views.md", "tables.md"]) == ("tables.md", "views.md")
