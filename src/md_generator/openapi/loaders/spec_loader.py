from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml


@dataclass(frozen=True, slots=True)
class LoadedSpec:
    """Path to a spec file on disk (YAML or JSON) and optional cleanup root."""

    path: Path
    cleanup_dir: Path | None = None


def _is_probably_openapi_name(name: str) -> bool:
    n = name.lower()
    return n.endswith("openapi.yaml") or n.endswith("openapi.yml") or n.endswith("openapi.json")


def _find_spec_in_directory(root: Path) -> Path:
    candidates: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if _is_probably_openapi_name(p.name):
            candidates.append(p)
    if not candidates:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".yaml", ".yml", ".json"):
                candidates.append(p)
    if not candidates:
        raise FileNotFoundError(f"No OpenAPI YAML/JSON under {root}")
    return candidates[0]


def _extract_zip(zip_path: Path) -> Path:
    td = Path(tempfile.mkdtemp(prefix="openapi-to-md-zip-"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(td)
    return _find_spec_in_directory(td)


def _download_url(url: str, timeout_s: float) -> Path:
    td = Path(tempfile.mkdtemp(prefix="openapi-to-md-url-"))
    parsed = urlparse(url)
    suffix = Path(parsed.path or "").suffix.lower()
    if suffix not in (".yaml", ".yml", ".json"):
        suffix = ".yaml"
    out = td / f"openapi{suffix}"
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        out.write_bytes(r.content)
    return out


def load_openapi_source(
    *,
    file: Path | None = None,
    folder: Path | None = None,
    zip_path: Path | None = None,
    url: str | None = None,
    url_timeout_s: float = 60.0,
) -> LoadedSpec:
    """Resolve exactly one input source to a local file path."""
    sources = [x for x in (file, folder, zip_path, url) if x is not None]
    if len(sources) != 1:
        raise ValueError("Specify exactly one of: file, folder, zip, url")

    if file is not None:
        p = file.expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(str(p))
        return LoadedSpec(path=p, cleanup_dir=None)

    if folder is not None:
        d = folder.expanduser().resolve()
        if not d.is_dir():
            raise NotADirectoryError(str(d))
        inner = _find_spec_in_directory(d)
        return LoadedSpec(path=inner, cleanup_dir=None)

    if zip_path is not None:
        zp = zip_path.expanduser().resolve()
        if not zp.is_file():
            raise FileNotFoundError(str(zp))
        td_root = Path(tempfile.mkdtemp(prefix="openapi-to-md-zip-"))
        with zipfile.ZipFile(zp, "r") as zf:
            zf.extractall(td_root)
        inner = _find_spec_in_directory(td_root)
        return LoadedSpec(path=inner, cleanup_dir=td_root)

    assert url is not None
    p = _download_url(url.strip(), url_timeout_s)
    return LoadedSpec(path=p, cleanup_dir=p.parent)


def sniff_and_parse_text(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"OpenAPI root must be an object: {path}")
    return data
