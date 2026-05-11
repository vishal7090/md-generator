"""Versioned JSON metadata under ``.codeflow_cache/_unified`` (TTL); semantic/git helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

_MANIFEST_VERSION = 1
_UNIFIED_SUBDIR = "_unified"


def unified_cache_root(project_root: Path) -> Path:
    return project_root.resolve() / ".codeflow_cache" / _UNIFIED_SUBDIR


def _hash_key(namespace: str, key_str: str) -> str:
    raw = f"{namespace}\0{key_str}".encode("utf-8", errors="replace")
    h = hashlib.sha256(raw).hexdigest()
    return h[:64]


def cache_path(project_root: Path, namespace: str, key_str: str) -> Path:
    return unified_cache_root(project_root) / namespace / f"{_hash_key(namespace, key_str)}.json"


def read_json_cache(project_root: Path, namespace: str, key_str: str) -> dict[str, Any] | None:
    path = cache_path(project_root, namespace, key_str)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("_manifest_version") != _MANIFEST_VERSION:
        return None
    exp = data.get("expires_at")
    if isinstance(exp, (int, float)) and time.time() > float(exp):
        return None
    return data


def write_json_cache(
    project_root: Path,
    namespace: str,
    key_str: str,
    payload: dict[str, Any],
    *,
    ttl_seconds: int = 0,
) -> None:
    path = cache_path(project_root, namespace, key_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {
        "_manifest_version": _MANIFEST_VERSION,
        **payload,
    }
    if ttl_seconds and ttl_seconds > 0:
        body["expires_at"] = time.time() + float(ttl_seconds)
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def clear_unified_cache(project_root: Path) -> None:
    p = unified_cache_root(project_root)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def clear_semantic_caches(project_root: Path, *, model_slug: str | None = None) -> None:
    """Remove ``.codeflow_cache/semantic`` (all models or one slug subdirectory)."""
    base = project_root.resolve() / ".codeflow_cache" / "semantic"
    if not base.exists():
        return
    if model_slug:
        d = base / model_slug
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        return
    shutil.rmtree(base, ignore_errors=True)


def apply_git_cache_clear() -> None:
    """Remove global Git clone cache (``~/.cache/codeflow/repos`` or ``CODEFLOW_GIT_CACHE``).

    Call from the CLI **before** ``clone_or_update_repo`` when using ``--cache-clear git|all`` with a
    remote URL so the active clone is not deleted after checkout.
    """
    from md_generator.codeflow.ingestion.git_loader import clean_all_cache

    clean_all_cache()


def apply_project_cache_clear(project_root: Path, mode: str | None) -> None:
    """Project-local ``.codeflow_cache`` subsets: ``semantic`` | ``unified`` | ``all`` (both).

    Git cache is handled by :func:`apply_git_cache_clear` (CLI / caller), not here, to avoid removing
    the workspace directory mid-scan.
    """
    if not mode or not str(mode).strip():
        return
    m = str(mode).strip().lower()
    if m == "unified":
        clear_unified_cache(project_root)
    elif m == "semantic":
        clear_semantic_caches(project_root)
    elif m == "all":
        clear_unified_cache(project_root)
        clear_semantic_caches(project_root)
