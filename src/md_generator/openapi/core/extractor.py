from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from md_generator.openapi.converters.swagger2_to_openapi3 import (
    convert_swagger2_to_openapi3,
    converted_document_to_json_bytes,
    is_swagger2_document,
)
from md_generator.openapi.core.run_config import ApiRunConfig
from md_generator.openapi.enrichers.rules import enrich_endpoints
from md_generator.openapi.loaders.spec_loader import load_openapi_source, sniff_and_parse_text
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


def _stringify_mapping_keys(obj: Any) -> tuple[Any, bool]:
    """Return (normalized_obj, changed) with all mapping keys coerced to strings."""
    if isinstance(obj, dict):
        changed = False
        out: dict[str, Any] = {}
        for k, v in obj.items():
            nk = k if isinstance(k, str) else str(k)
            nv, ch = _stringify_mapping_keys(v)
            if nk != k or ch:
                changed = True
            out[nk] = nv
        return out, changed
    if isinstance(obj, list):
        changed = False
        out_list: list[Any] = []
        for v in obj:
            nv, ch = _stringify_mapping_keys(v)
            if ch:
                changed = True
            out_list.append(nv)
        return out_list, changed
    return obj, False


def _collect_path_tokens(path_key: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"\{([^}]+)\}", path_key)}


def _resolve_parameter_candidate(param: Any, component_parameters: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(param, dict):
        return None
    ref = param.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/parameters/"):
        key = ref.split("/")[-1]
        resolved = component_parameters.get(key)
        return resolved if isinstance(resolved, dict) else None
    return param


def _prune_invalid_openapi_path_parameters(doc: dict[str, Any]) -> bool:
    """Drop path parameters whose names are not present in the corresponding path template."""
    methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return False
    component_parameters = ((doc.get("components") or {}).get("parameters") or {})
    if not isinstance(component_parameters, dict):
        component_parameters = {}
    changed = False

    def _prune_params(params: Any, allowed_tokens: set[str]) -> Any:
        nonlocal changed
        if not isinstance(params, list):
            return params
        out: list[Any] = []
        for p in params:
            keep = True
            cand = _resolve_parameter_candidate(p, component_parameters)
            if isinstance(cand, dict) and str(cand.get("in") or "") == "path":
                name = str(cand.get("name") or "")
                if name and name not in allowed_tokens:
                    keep = False
            if keep:
                out.append(p)
        if len(out) != len(params):
            changed = True
        return out

    for path_key, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        allowed_tokens = _collect_path_tokens(str(path_key))
        if "parameters" in path_item:
            path_item["parameters"] = _prune_params(path_item.get("parameters"), allowed_tokens)
        for method, op in path_item.items():
            if str(method).lower() not in methods or not isinstance(op, dict):
                continue
            if "parameters" in op:
                op["parameters"] = _prune_params(op.get("parameters"), allowed_tokens)
    return changed


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
    conversion_dir: Path | None = None
    try:
        raw = sniff_and_parse_text(loaded.path)
        path_for_resolve = loaded.path
        if is_swagger2_document(raw):
            _emit(on_progress, 4, "convert_swagger2")
            converted = convert_swagger2_to_openapi3(raw)
            conversion_dir = Path(tempfile.mkdtemp(prefix="openapi-sw2-"))
            conv_path = conversion_dir / "openapi.converted.json"
            conv_path.write_bytes(converted_document_to_json_bytes(converted))
            path_for_resolve = conv_path
        else:
            normalized_raw, changed = _stringify_mapping_keys(raw)
            changed = _prune_invalid_openapi_path_parameters(normalized_raw) or changed
            if changed:
                _emit(on_progress, 4, "normalize_input")
                conversion_dir = Path(tempfile.mkdtemp(prefix="openapi-norm-"))
                conv_path = conversion_dir / "openapi.normalized.json"
                conv_path.write_bytes(converted_document_to_json_bytes(normalized_raw))
                path_for_resolve = conv_path
        _emit(on_progress, 5, "resolve_refs")
        resolved = resolve_openapi_file(path_for_resolve, strict=True)
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
        if conversion_dir and conversion_dir.is_dir():
            try:
                shutil.rmtree(conversion_dir, ignore_errors=True)
            except Exception:
                logger.debug("cleanup failed for %s", conversion_dir, exc_info=True)
        if loaded.cleanup_dir and loaded.cleanup_dir.is_dir():
            try:
                shutil.rmtree(loaded.cleanup_dir, ignore_errors=True)
            except Exception:
                logger.debug("cleanup failed for %s", loaded.cleanup_dir, exc_info=True)
