"""Compose detectors and merge entry records onto parse results."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.config.codeflow_yaml import (
    load_codeflow_yaml,
    portlet_base_classes_from_yaml,
    resolve_codeflow_config_path,
)
from md_generator.codeflow.detectors.api_detector import detect_api_entries
from md_generator.codeflow.detectors.kafka_detector import detect_kafka_entries
from md_generator.codeflow.detectors.liferay_portlet_detector import detect_liferay_portlet_entries
from md_generator.codeflow.models.ir import EntryKind, EntryRecord, FileParseResult

# TYPE_CHECKING would avoid circular import; ScanConfig is lightweight dataclass
from md_generator.codeflow.core.run_config import ScanConfig


def _merged_extra_portlet_bases(project_root: Path, cfg: ScanConfig | None) -> frozenset[str]:
    extra: set[str] = set()
    if cfg and cfg.liferay_portlet_base_classes:
        extra.update(str(x).strip() for x in cfg.liferay_portlet_base_classes if str(x).strip())
    ypath = resolve_codeflow_config_path(project_root.resolve(), cfg.codeflow_config_path if cfg else None)
    if ypath:
        data = load_codeflow_yaml(ypath)
        extra.update(portlet_base_classes_from_yaml(data))
    return frozenset(extra)


def apply_entry_detectors(
    paths: list[Path],
    project_root: Path,
    results: list[FileParseResult],
    cfg: ScanConfig | None = None,
) -> None:
    """Mutate ``results`` in place with additional ``EntryRecord`` rows."""
    by_path = {r.path.resolve(): r for r in results}
    portlet_extras = _merged_extra_portlet_bases(project_root, cfg)
    for p in paths:
        pr = by_path.get(p.resolve())
        if not pr:
            continue
        pr.entries.extend(detect_api_entries(p, project_root))
        pr.entries.extend(detect_liferay_portlet_entries(p, project_root, extra_portlet_bases=portlet_extras))
        pr.entries.extend(detect_kafka_entries(p, project_root))


def filter_entries_by_include(
    entries: list[EntryRecord],
    include_kinds: set[str] | None,
    exclude_internal: bool,
) -> list[EntryRecord]:
    """include_kinds uses EntryKind value strings, e.g. {\"api_rest\",\"main\"}."""
    out: list[EntryRecord] = []
    for e in entries:
        k = e.kind.value
        if include_kinds and k not in include_kinds:
            continue
        if exclude_internal and k == EntryKind.UNKNOWN.value:
            continue
        out.append(e)
    return out


def resolve_entry_symbol_ids(
    explicit: list[str] | None,
    detected: list[EntryRecord],
) -> list[str]:
    if explicit:
        return list(explicit)
    return list({e.symbol_id for e in detected})
