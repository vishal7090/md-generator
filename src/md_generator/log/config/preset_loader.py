from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_PACKAGE_PRESETS = "md_generator.log.config.presets"


def default_user_preset_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("MD_LOG_PRESET_DIRS", "").strip()
    if env:
        for part in env.split(os.pathsep):
            p = Path(part).expanduser()
            if p.is_dir():
                dirs.append(p.resolve())
    home = Path.home() / ".mdengine" / "log" / "presets"
    if home.is_dir():
        dirs.append(home.resolve())
    cwd = Path.cwd() / "log-presets"
    if cwd.is_dir():
        dirs.append(cwd.resolve())
    return dirs


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _package_preset_path(name: str) -> Path | None:
    import importlib.resources as ir

    try:
        return Path(str(ir.files(_PACKAGE_PRESETS).joinpath(f"{name}.yaml")))
    except (FileNotFoundError, OSError, TypeError):
        return None


def resolve_preset_path(name: str, extra_dirs: list[str] | None = None) -> Path | None:
    """Find preset YAML by name in user dirs then packaged presets."""
    fname = f"{name}.yaml"
    for d in list(extra_dirs or []) + [str(p) for p in default_user_preset_dirs()]:
        candidate = Path(d).expanduser() / fname
        if candidate.is_file():
            return candidate.resolve()
    pkg = _package_preset_path(name)
    if pkg is not None and pkg.is_file():
        return pkg
    return None


def load_preset_by_name(name: str, extra_dirs: list[str] | None = None) -> dict[str, Any]:
    path = resolve_preset_path(name, extra_dirs)
    if path is None:
        return {}
    return _load_yaml_file(path)


def list_preset_names(extra_dirs: list[str] | None = None) -> list[str]:
    seen: dict[str, None] = {}
    dirs: list[Path] = []
    for d in list(extra_dirs or []) + [str(p) for p in default_user_preset_dirs()]:
        p = Path(d).expanduser()
        if p.is_dir():
            dirs.append(p.resolve())
    import importlib.resources as ir

    try:
        pkg_root = ir.files(_PACKAGE_PRESETS)
        for entry in pkg_root.iterdir():
            if entry.name.endswith(".yaml"):
                seen[entry.name[:-5]] = None
    except (FileNotFoundError, OSError, TypeError):
        pass
    for d in dirs:
        for f in sorted(d.glob("*.yaml")):
            seen[f.stem] = None
    return sorted(seen.keys())
