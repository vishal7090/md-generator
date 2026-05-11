from __future__ import annotations

import time
from pathlib import Path

from md_generator.codeflow.core.cache_manager import (
    apply_project_cache_clear,
    clear_semantic_caches,
    read_json_cache,
    write_json_cache,
)


def test_cache_manager_ttl_expired_returns_none(tmp_path: Path) -> None:
    write_json_cache(tmp_path, "ns", "k1", {"x": 1}, ttl_seconds=1)
    hit = read_json_cache(tmp_path, "ns", "k1")
    assert hit is not None and hit.get("x") == 1
    time.sleep(1.15)
    assert read_json_cache(tmp_path, "ns", "k1") is None


def test_cache_manager_persist_without_ttl(tmp_path: Path) -> None:
    write_json_cache(tmp_path, "ns", "k2", {"y": 2}, ttl_seconds=0)
    h = read_json_cache(tmp_path, "ns", "k2")
    assert h is not None and h.get("y") == 2


def test_semantic_clear_removes_slug_dir(tmp_path: Path) -> None:
    sem = tmp_path / ".codeflow_cache" / "semantic" / "mymodel"
    sem.mkdir(parents=True)
    (sem / "manifest.json").write_text("{}", encoding="utf-8")
    clear_semantic_caches(tmp_path, model_slug="mymodel")
    assert not sem.exists()


def test_apply_project_cache_clear_all(tmp_path: Path) -> None:
    uni = tmp_path / ".codeflow_cache" / "_unified" / "x"
    uni.mkdir(parents=True)
    (uni / "f.json").write_text("{}", encoding="utf-8")
    sem = tmp_path / ".codeflow_cache" / "semantic" / "z"
    sem.mkdir(parents=True)
    apply_project_cache_clear(tmp_path, "all")
    assert not (tmp_path / ".codeflow_cache" / "_unified").exists()
    assert not (tmp_path / ".codeflow_cache" / "semantic").exists()
