from __future__ import annotations

import hashlib
import json
from typing import Any

from md_generator.core.artifacts.models import MarkdownArtifact
from md_generator.log.parser.models import LogRecord


def config_hash(cfg_blob: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(cfg_blob, sort_keys=True, default=str).encode()).hexdigest()[:16]


def apply_lineage(
    artifacts: list[MarkdownArtifact],
    *,
    config_hash: str,
    source_file: str | None = None,
) -> list[MarkdownArtifact]:
    for art in artifacts:
        art.metadata.lineage.setdefault("config_hash", config_hash)
        if source_file:
            art.metadata.lineage.setdefault("source_file", source_file)
    return artifacts


def lineage_from_record(r: LogRecord) -> dict[str, Any]:
    md = r.metadata or {}
    return {
        "source_file": str(md.get("source_file", r.source_file)),
        "line_number": r.line_number,
        "zip_member": md.get("zip_member"),
    }
