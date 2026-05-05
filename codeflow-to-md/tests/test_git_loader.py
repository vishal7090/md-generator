from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from md_generator.codeflow.ingestion.git_loader import (
    GitLoaderError,
    cache_dir_for_url,
    clean_all_cache,
    clone_or_update_repo,
    default_cache_root,
    is_git_remote,
)


@pytest.mark.parametrize(
    ("s", "expect"),
    [
        ("https://github.com/foo/bar.git", True),
        ("https://github.com/foo/bar", True),
        ("https://gitlab.com/a/b.git", True),
        ("https://bitbucket.org/a/b", True),
        ("https://dev.azure.com/org/proj/_git/repo", True),
        ("git@github.com:foo/bar.git", True),
        ("ssh://git@gitlab.com/foo/bar.git", True),
        ("/home/user/proj", False),
        ("C:\\\\temp\\\\repo", False),
        ("./relative", False),
        ("https://example.com/page.html", False),
    ],
)
def test_is_git_remote(s: str, expect: bool) -> None:
    assert is_git_remote(s) is expect


def test_cache_dir_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEFLOW_GIT_CACHE", str(tmp_path / "c"))
    u = "https://github.com/foo/bar.git"
    assert cache_dir_for_url(u) == cache_dir_for_url(u)
    assert cache_dir_for_url(u).parent == default_cache_root()


def test_clean_all_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEFLOW_GIT_CACHE", str(tmp_path))
    d = tmp_path / "x"
    d.mkdir()
    (d / "f").write_text("a", encoding="utf-8")
    clean_all_cache()
    assert not d.exists()


def test_clone_or_update_fresh_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEFLOW_GIT_CACHE", str(tmp_path / "cache"))
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["git", "--version"]:
            return mock.MagicMock(returncode=0, stdout="git 2", stderr="")
        if cmd[:2] == ["git", "clone"]:
            dest = Path(cmd[-1])
            dest.mkdir(parents=True)
            return mock.MagicMock(returncode=0, stdout="", stderr="")
        return mock.MagicMock(returncode=0, stdout="", stderr="")

    with mock.patch("md_generator.codeflow.ingestion.git_loader.subprocess.run", side_effect=fake_run):
        out = clone_or_update_repo("https://github.com/foo/bar.git", branch="main")

    assert out.is_dir()
    assert any(c[:3] == ["git", "clone", "--depth"] for c in calls)


def test_clone_or_update_no_cache_removes_then_clones(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEFLOW_GIT_CACHE", str(tmp_path / "cache"))
    repo = cache_dir_for_url("https://github.com/x/y.git")
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()

    seq: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seq.append(list(cmd))
        if cmd[:2] == ["git", "--version"]:
            return mock.MagicMock(returncode=0, stdout="git 2", stderr="")
        if cmd[:2] == ["git", "clone"]:
            Path(cmd[-1]).mkdir(parents=True)
            return mock.MagicMock(returncode=0, stdout="", stderr="")
        return mock.MagicMock(returncode=0, stdout="", stderr="")

    with mock.patch("md_generator.codeflow.ingestion.git_loader.subprocess.run", side_effect=fake_run):
        clone_or_update_repo("https://github.com/x/y.git", no_cache=True)

    assert any(c[:2] == ["git", "clone"] for c in seq)


def test_git_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(cmd, **kwargs):
        raise FileNotFoundError()

    with mock.patch("md_generator.codeflow.ingestion.git_loader.subprocess.run", side_effect=boom):
        with pytest.raises(GitLoaderError, match="git"):
            clone_or_update_repo("https://github.com/a/b.git")
