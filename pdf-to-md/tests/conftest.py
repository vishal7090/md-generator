"""Pytest fixtures: ensure minimal.pdf exists."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal.pdf"


@pytest.fixture(scope="session", autouse=True)
def _ensure_minimal_pdf() -> None:
    if _FIXTURE.is_file():
        return
    mod_path = Path(__file__).resolve().parent / "build_fixture.py"
    spec = importlib.util.spec_from_file_location("_pdf_build_fixture", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.build_minimal_pdf(_FIXTURE)
    assert _FIXTURE.is_file(), f"failed to create {_FIXTURE}"


@pytest.fixture
def minimal_pdf_path() -> Path:
    assert _FIXTURE.is_file()
    return _FIXTURE
