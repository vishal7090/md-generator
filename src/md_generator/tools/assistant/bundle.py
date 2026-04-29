from __future__ import annotations

import os
from pathlib import Path


def ai_root() -> Path:
    """Directory containing `registry.json`, `dependency-graph.json`, and `skills/`."""
    env = os.environ.get("MDENGINE_SKILL_AI_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent / "data"
