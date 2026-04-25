from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ApiRunConfig:
    file: Path | None = None
    folder: Path | None = None
    zip: Path | None = None
    url: str | None = None
    output_path: Path = field(default_factory=lambda: Path("docs"))
    formats: tuple[str, ...] = ("md", "mermaid")
    preferred_media_type: str = "application/json"
    url_timeout_s: float = 60.0

    def with_output(self, path: Path) -> ApiRunConfig:
        return replace(self, output_path=path)

    def formats_set(self) -> frozenset[str]:
        xs = tuple(str(x).strip().lower() for x in self.formats if str(x).strip())
        if not xs:
            return frozenset({"md"})
        return frozenset(xs)

    def normalized(self) -> ApiRunConfig:
        fmts = tuple(sorted({str(x).strip().lower() for x in self.formats if str(x).strip()}))
        if not fmts:
            fmts = ("md",)
        to = float(self.url_timeout_s)
        if to <= 0:
            to = 60.0
        pm = (self.preferred_media_type or "application/json").strip() or "application/json"
        return ApiRunConfig(
            file=self.file,
            folder=self.folder,
            zip=self.zip,
            url=self.url,
            output_path=Path(self.output_path),
            formats=fmts,
            preferred_media_type=pm,
            url_timeout_s=to,
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_api_run_config(path: Path | None, overrides: dict[str, Any] | None = None) -> ApiRunConfig:
    raw: dict[str, Any] = {}
    if path is not None and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path is None:
        try:
            import importlib.resources as ir

            txt = ir.files("md_generator.openapi.config").joinpath("default.yaml").read_text(encoding="utf-8")
            raw = yaml.safe_load(txt) or {}
        except Exception:
            raw = {}
    if overrides:
        raw = _deep_merge(raw, overrides)

    inp = raw.get("input") or {}
    out = raw.get("output") or {}
    oa = raw.get("openapi") or {}

    def _p(key: str) -> Path | None:
        v = inp.get(key)
        return Path(str(v)).expanduser() if v else None

    url = inp.get("url")
    url_s = str(url).strip() if url else None

    fmts = out.get("formats") or ["md", "mermaid"]
    if isinstance(fmts, str):
        fmts = [fmts]

    return ApiRunConfig(
        file=_p("file"),
        folder=_p("folder"),
        zip=_p("zip"),
        url=url_s,
        output_path=Path(str(out.get("path", "./docs"))),
        formats=tuple(str(x) for x in fmts),
        preferred_media_type=str(oa.get("preferred_media_type", "application/json")),
        url_timeout_s=float(inp.get("url_timeout_s", 60.0)),
    ).normalized()
