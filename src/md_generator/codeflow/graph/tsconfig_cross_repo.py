"""Deterministic ``tsconfig`` / ``jsconfig`` ``paths`` expansion for cross-repo import candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_tsconfig_paths_map(repo_root: Path) -> dict[str, list[str]]:
    """Map path pattern prefix (e.g. ``@app/*``) to list of posix path templates under repo root.

    Uses ``compilerOptions.paths`` and ``baseUrl`` (default ``.``). Targets ending in ``*`` append
    the unmatched suffix of the module string.
    """
    rr = repo_root.resolve()
    for name in ("tsconfig.json", "jsconfig.json"):
        p = rr / name
        if not p.is_file():
            continue
        data = _read_json(p)
        if not data:
            continue
        co = data.get("compilerOptions")
        if not isinstance(co, dict):
            continue
        base = str(co.get("baseUrl") or ".").strip().replace("\\", "/").rstrip("/")
        base_dir = rr if base in (".", "") else (rr / base).resolve()
        paths = co.get("paths")
        if not isinstance(paths, dict):
            continue
        out: dict[str, list[str]] = {}
        for key, val in paths.items():
            k = str(key).strip().replace("\\", "/")
            if not k:
                continue
            targets: list[str] = []
            if isinstance(val, list):
                for item in val:
                    if not isinstance(item, str):
                        continue
                    t = item.strip().replace("\\", "/")
                    if not t:
                        continue
                    abs_t = (base_dir / t).resolve()
                    try:
                        posix = abs_t.relative_to(rr).as_posix()
                    except ValueError:
                        posix = t
                    targets.append(posix)
            if targets:
                out[k] = targets
        return out
    return {}


def _strip_star(s: str) -> str:
    return s[:-2] if s.endswith("/*") else s


def expand_module_with_tsconfig_paths(mod: str, paths_map: dict[str, list[str]]) -> list[str]:
    """Turn ``@scope/foo/bar`` into candidate posix rel paths using ``paths`` keys (longest key first)."""
    if not mod or not paths_map:
        return []
    mod = mod.replace("\\", "/")
    cands: list[str] = []
    keys = sorted(paths_map.keys(), key=len, reverse=True)
    for pat in keys:
        pfx = _strip_star(pat)
        if pat.endswith("/*"):
            if mod == pfx or mod.startswith(pfx + "/"):
                suffix = mod[len(pfx) :].lstrip("/")
                for base in paths_map[pat]:
                    b = _strip_star(base)
                    if base.endswith("/*"):
                        if suffix:
                            cands.append(f"{b}/{suffix}".replace("//", "/"))
                    else:
                        cands.append(base)
        elif mod == pfx or mod.startswith(pat + "/"):
            for base in paths_map[pat]:
                cands.append(base)
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        c = c.strip().replace("//", "/")
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def tsconfig_candidate_files(rel_stem: str) -> list[str]:
    """Given a path without extension, return ordered candidate file paths."""
    base = rel_stem.replace("//", "/").rstrip("/")
    if not base:
        return []
    return [
        f"{base}.ts",
        f"{base}.tsx",
        f"{base}.js",
        f"{base}.jsx",
        f"{base}.mjs",
        f"{base}/index.ts",
        f"{base}/index.tsx",
        f"{base}/index.js",
    ]


def collect_tsconfig_maps_by_repo_label(
    roots_with_labels: list[tuple[str, Path]],
) -> dict[str, dict[str, list[str]]]:
    """``repo_label`` -> paths map from :func:`load_tsconfig_paths_map`."""
    acc: dict[str, dict[str, list[str]]] = {}
    for lab, root in roots_with_labels:
        m = load_tsconfig_paths_map(root.resolve())
        if m:
            acc[lab] = m
    return acc
