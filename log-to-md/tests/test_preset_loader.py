from __future__ import annotations

from pathlib import Path

from md_generator.log.config.preset_loader import list_preset_names, load_preset_by_name, resolve_preset_path
from md_generator.log.core.run_config import load_run_config
from md_generator.log.parser.parser_registry import select_preset_for_sample


def test_user_preset_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    presets = tmp_path / "log-presets"
    presets.mkdir()
    (presets / "custom.yaml").write_text(
        "parser:\n  preset: custom\n  line_regex: '^(?P<level>INFO) (?P<message>.*)$'\n",
        encoding="utf-8",
    )
    assert resolve_preset_path("custom") is not None
    data = load_preset_by_name("custom")
    assert "parser" in data
    assert "custom" in list_preset_names()


def test_load_run_config_user_preset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    presets = tmp_path / "log-presets"
    presets.mkdir()
    (presets / "bracket.yaml").write_text(
        "parser:\n  preset: bracket\n  line_regex: '^(?P<level>ERROR) (?P<message>.*)$'\n",
        encoding="utf-8",
    )
    log = tmp_path / "t.log"
    log.write_text("ERROR something broke\n", encoding="utf-8")
    cfg = load_run_config(
        None,
        {
            "input": {"paths": [str(log)]},
            "parser": {"preset": "bracket"},
            "output": {"path": str(tmp_path / "out")},
        },
    )
    assert cfg.parser.line_regex


def test_auto_detect_json_line() -> None:
    sample = '{"level":"ERROR","message":"x"}\n{"level":"INFO","message":"y"}\n'
    assert select_preset_for_sample(sample) == "json"
