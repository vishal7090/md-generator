from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _set_ai_root() -> None:
    os.environ["MDENGINE_SKILL_AI_ROOT"] = str(_REPO_ROOT / "ai")
