from __future__ import annotations

from pathlib import Path

from md_generator.db.core.models import FEATURES
from md_generator.db.core.run_config import RunConfig, load_run_config


def test_load_run_config_merge(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text(
        """
database:
  type: mysql
  uri: mysql://localhost/db
output:
  path: ./out
features:
  exclude: [triggers]
""",
        encoding="utf-8",
    )
    cfg = load_run_config(
        p,
        {"database": {"schema": "app"}, "limits": {"max_tables": 3}},
    )
    assert cfg.db_type == "mysql"
    assert cfg.schema == "app"
    assert "triggers" in cfg.exclude
    assert cfg.limits.get("max_tables") == 3


def test_effective_features_respects_exclude() -> None:
    cfg = RunConfig(
        db_type="postgres",
        uri="x",
        include=frozenset({"tables", "views"}),
        exclude=frozenset({"views"}),
    )
    assert cfg.effective_features() == frozenset({"tables"})


def test_default_include_all_features() -> None:
    cfg = RunConfig(db_type="postgres", uri="postgresql://localhost/x", schema="public")
    assert cfg.effective_features() == FEATURES


def test_default_erd_config_from_packaged_yaml() -> None:
    cfg = load_run_config(None, None)
    assert cfg.erd.max_tables == 100
    assert cfg.erd.scope == "full"


def test_readme_merge_inline_auto_enables_combined_when_split(tmp_path: Path) -> None:
    p = tmp_path / "o.yaml"
    p.write_text(
        """
database:
  type: postgres
  uri: postgresql://localhost/x
  schema: public
output:
  split_files: true
  write_combined_feature_markdown: false
  readme_feature_merge: inline
""",
        encoding="utf-8",
    )
    cfg = load_run_config(p, None)
    assert cfg.write_combined_feature_markdown is True
    assert cfg.readme_feature_merge == "inline"


def test_erd_partial_yaml_merge(tmp_path: Path) -> None:
    p = tmp_path / "e.yaml"
    p.write_text(
        """
database:
  type: postgres
  uri: postgresql://localhost/x
  schema: public
erd:
  max_tables: 7
""",
        encoding="utf-8",
    )
    cfg = load_run_config(p, None)
    assert cfg.erd.max_tables == 7
    assert cfg.erd.scope == "full"
