"""Optional ``codeflow.yaml`` beside the project root for codeflow scan hints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_codeflow_yaml(path: Path) -> dict[str, Any]:
    """Load YAML if the file exists and PyYAML is available; otherwise return {}."""
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        logger.debug("PyYAML not installed; skip %s", path)
        return {}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.debug("codeflow yaml load failed %s: %s", path, e)
        return {}


def portlet_base_classes_from_yaml(data: dict[str, Any]) -> frozenset[str]:
    lif = data.get("liferay")
    if not isinstance(lif, dict):
        return frozenset()
    raw = lif.get("portlet_base_classes")
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(x).strip() for x in raw if str(x).strip())


def resolve_codeflow_config_path(project_root: Path, explicit: Path | None) -> Path | None:
    """Return path to try loading, or None if no file to load."""
    if explicit is not None:
        return explicit if explicit.is_file() else None
    cand = project_root.resolve() / "codeflow.yaml"
    return cand if cand.is_file() else None
