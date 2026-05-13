from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from md_generator.log.config.schemas import (
    AggregationSection,
    ChunkSection,
    ChunkingSection,
    ClusteringSection,
    CorrelationSection,
    EmbeddingsSection,
    ExecutionSection,
    IncidentsSection,
    InputSection,
    IntelligenceSection,
    KnowledgeGraphSection,
    LogRunConfig,
    NormalizationSection,
    OutputSection,
    ParserSection,
    PluginsSection,
    SearchSection,
    TimelineSection,
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _section(
    raw: dict[str, Any],
    key: str,
    cls: type,
    defaults: dict[str, Any],
) -> Any:
    data = {**defaults, **(raw.get(key) or {})}
    return cls(**{k: data[k] for k in cls.__dataclass_fields__.keys() if k in data})  # type: ignore[attr-defined]


def _dict_from_dataclass(obj: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(obj)


def log_config_to_jsonable(cfg: LogRunConfig) -> dict[str, Any]:
    return _dict_from_dataclass(cfg)


def jsonable_to_log_config(data: dict[str, Any]) -> LogRunConfig:
    """Rebuild LogRunConfig from JSON (job persistence)."""
    return _config_from_raw(data)


def _config_from_raw(raw: dict[str, Any]) -> LogRunConfig:
    return LogRunConfig(
        input=_section(raw, "input", InputSection, {"paths": []}),
        parser=_section(
            raw,
            "parser",
            ParserSection,
            {
                "preset": "generic",
                "line_regex": None,
                "fuzzy_timestamp": False,
                "auto_detect": False,
            },
        ),
        normalization=_section(
            raw,
            "normalization",
            NormalizationSection,
            {
                "redact_pii": False,
                "normalize_numbers": False,
                "normalize_uuid": False,
                "normalize_paths": False,
            },
        ),
        aggregation=_section(raw, "aggregation", AggregationSection, {"timeline": "hourly"}),
        clustering=_section(
            raw,
            "clustering",
            ClusteringSection,
            {
                "enabled": False,
                "algorithm": "kmeans",
                "n_clusters": 8,
                "random_state": 42,
                "max_features": 4096,
            },
        ),
        output=_section(
            raw,
            "output",
            OutputSection,
            {
                "path": "./log-docs",
                "split_by_level": True,
                "generate_incidents": True,
                "generate_clusters": False,
                "generate_chunks": False,
            },
        ),
        chunk=_section(
            raw,
            "chunk",
            ChunkSection,
            {"enabled": False, "lines_per_chunk": 100_000, "records_per_md_chunk": 500},
        ),
        execution=_section(
            raw,
            "execution",
            ExecutionSection,
            {
                "workers": 4,
                "max_lines_per_file": None,
                "encoding_fallbacks": ["utf-8", "utf-8-sig", "latin-1", "cp1252"],
            },
        ),
        plugins=_section(raw, "plugins", PluginsSection, {"enrichers": [], "parsers": [], "writers": [], "classifiers": []}),
        incidents=_section(
            raw,
            "incidents",
            IncidentsSection,
            {"min_occurrences": 2, "levels": ["ERROR", "FATAL", "WARN"], "stacktrace_aware": True},
        ),
        chunking=_section(
            raw,
            "chunking",
            ChunkingSection,
            {
                "enabled": False,
                "strategies": ["incident", "timeline", "stacktrace", "cluster", "service"],
                "chunk_id_namespace": "chunk",
                "max_chunk_bytes": 256_000,
            },
        ),
        embeddings=_section(
            raw,
            "embeddings",
            EmbeddingsSection,
            {"enabled": False, "exporters": [], "output_subdir": "embeddings"},
        ),
        correlation=_section(
            raw,
            "correlation",
            CorrelationSection,
            {"enabled": False, "timeline_window_seconds": 300},
        ),
        knowledge_graph=_section(
            raw,
            "knowledge_graph",
            KnowledgeGraphSection,
            {"enabled": False, "mermaid": True},
        ),
        timeline=_section(
            raw,
            "timeline",
            TimelineSection,
            {"enabled": False, "causal_window_seconds": 120},
        ),
        intelligence=_section(raw, "intelligence", IntelligenceSection, {"enabled": False}),
        search=_section(raw, "search", SearchSection, {"index_path": None}),
    )


def load_preset(name: str) -> dict[str, Any]:
    """Load YAML preset fragment (parser overrides)."""
    import importlib.resources as ir

    pkg = "md_generator.log.config.presets"
    fname = f"{name}.yaml"
    try:
        txt = ir.files(pkg).joinpath(fname).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    loaded = yaml.safe_load(txt) or {}
    return loaded if isinstance(loaded, dict) else {}


def load_run_config(path: Path | None, overrides: dict[str, Any] | None = None) -> LogRunConfig:
    raw: dict[str, Any] = {}
    if path is not None and path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif path is None:
        try:
            import importlib.resources as ir

            txt = ir.files("md_generator.log.config").joinpath("default.yaml").read_text(encoding="utf-8")
            raw = yaml.safe_load(txt) or {}
        except Exception:
            raw = {}
    if overrides:
        raw = _deep_merge(raw, overrides)
    preset_name = str((raw.get("parser") or {}).get("preset") or "generic").strip() or "generic"
    preset_data = load_preset(preset_name)
    if preset_data:
        raw = _deep_merge(preset_data, raw)
    return _config_from_raw(raw).normalized()
