from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from md_generator.db.core.models import RunMetadata
from md_generator.db.core.run_config import RunConfig


@dataclass
class ExportManifestBuilder:
    """Collect export statistics and file paths for ``export_manifest.json``."""

    counts: dict[str, int] = field(default_factory=dict)
    generated_files: list[str] = field(default_factory=list)
    combined_bundles: list[str] = field(default_factory=list)
    dependency_edges: int = 0

    def add_file(self, path: Path, output_root: Path) -> None:
        try:
            rel = path.resolve().relative_to(output_root.resolve()).as_posix()
        except ValueError:
            rel = path.name
        if rel not in self.generated_files:
            self.generated_files.append(rel)

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def to_dict(
        self,
        cfg: RunConfig,
        meta: RunMetadata,
        *,
        database_name: str | None = None,
    ) -> dict[str, Any]:
        return {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "database_type": meta.db_type,
            "database": database_name,
            "schema": meta.schema,
            "uri_display": meta.uri_display,
            "included_features": list(meta.included_features),
            "counts": dict(sorted(self.counts.items())),
            "dependency_edges": self.dependency_edges,
            "generated_files": sorted(self.generated_files),
            "combined_bundles": sorted(self.combined_bundles),
            "erd_artifacts": list(meta.erd_artifacts),
            "limits": meta.limits,
            "output": {
                "split_files": cfg.split_files,
                "write_manifest": cfg.write_manifest,
                "markdown_cross_links": cfg.markdown_cross_links,
            },
        }

    def write(self, output_root: Path, cfg: RunConfig, meta: RunMetadata) -> Path:
        data = self.to_dict(cfg, meta)
        p = output_root / "export_manifest.json"
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.add_file(p, output_root)
        return p
