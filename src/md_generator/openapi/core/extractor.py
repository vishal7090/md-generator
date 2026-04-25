from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable

from md_generator.openapi.core.run_config import ApiRunConfig
from md_generator.openapi.enrichers.rules import enrich_endpoints
from md_generator.openapi.loaders.spec_loader import load_openapi_source
from md_generator.openapi.models.domain import ApiSpecMeta
from md_generator.openapi.normalizers.operations import build_endpoint_docs, load_security_schemes
from md_generator.openapi.normalizers.schema_flatten import flatten_schema
from md_generator.openapi.parsers.openapi_parser import parse_openapi_dict, validate_openapi_version
from md_generator.openapi.resolvers.ref_resolver import resolve_openapi_file
from md_generator.openapi.writers.markdown_writer import write_api_markdown_tree, write_schema_files

logger = logging.getLogger(__name__)


def _emit(on_progress: Callable[[int, str], None] | None, pct: int, cur: str) -> None:
    if on_progress:
        on_progress(pct, cur)


def extract_to_markdown(
    cfg: ApiRunConfig,
    *,
    on_progress: Callable[[int, str], None] | None = None,
    on_file: Callable[[Path], None] | None = None,
) -> ApiSpecMeta:
    cfg = cfg.normalized()
    loaded = load_openapi_source(
        file=cfg.file,
        folder=cfg.folder,
        zip_path=cfg.zip,
        url=cfg.url,
        url_timeout_s=cfg.url_timeout_s,
    )
    try:
        _emit(on_progress, 5, "resolve_refs")
        resolved = resolve_openapi_file(loaded.path, strict=True)
        parse_openapi_dict(resolved)
        schemes = load_security_schemes(resolved)
        _emit(on_progress, 25, "normalize_operations")
        endpoints = build_endpoint_docs(resolved, preferred_media_type=cfg.preferred_media_type)
        info = resolved.get("info") or {}
        title = str(info.get("title") or "API")
        version = str(info.get("version") or "")
        openapi_v = validate_openapi_version(resolved)
        servers_raw = resolved.get("servers") or []
        servers: list[str] = []
        if isinstance(servers_raw, list):
            for s in servers_raw:
                if isinstance(s, dict) and isinstance(s.get("url"), str):
                    servers.append(s["url"])
        _emit(on_progress, 45, "enrich")
        endpoints = enrich_endpoints(endpoints, security_schemes=schemes, api_title=title)
        meta = ApiSpecMeta(
            title=title,
            version=version,
            openapi_version=openapi_v,
            servers=tuple(servers),
            security_schemes=schemes,
            endpoints=endpoints,
            raw_spec_path=loaded.path,
        )
        out = Path(cfg.output_path)
        out.mkdir(parents=True, exist_ok=True)
        _emit(on_progress, 60, "write_markdown")
        fmts = cfg.formats_set()
        write_api_markdown_tree(meta, out, formats=fmts)
        comps = (resolved.get("components") or {}).get("schemas") or {}
        flat_schemas: dict[str, dict] = {}
        if isinstance(comps, dict):
            for name in sorted(comps.keys()):
                sch = comps[name]
                if isinstance(sch, dict):
                    fs = flatten_schema(sch)
                    if isinstance(fs, dict):
                        flat_schemas[name] = fs
        write_schema_files(out, flat_schemas, formats=fmts)
        _emit(on_progress, 95, "done")
        if on_file:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    on_file(p)
        return meta
    finally:
        if loaded.cleanup_dir and loaded.cleanup_dir.is_dir():
            try:
                shutil.rmtree(loaded.cleanup_dir, ignore_errors=True)
            except Exception:
                logger.debug("cleanup failed for %s", loaded.cleanup_dir, exc_info=True)
