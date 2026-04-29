from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .bundle import ai_root


@dataclass
class LoadedRegistry:
    raw: dict
    root: Path

    @property
    def schema_version(self) -> str:
        return str(self.raw.get("schemaVersion", ""))

    @property
    def bundle_version(self) -> str:
        return str(self.raw.get("bundleVersion", ""))


class Registry:
    """Load `registry.json` and resolve keyword → area → skill id."""

    def __init__(self, loaded: LoadedRegistry) -> None:
        self._loaded = loaded

    @classmethod
    def load(cls, ai_directory: Path | None = None) -> Registry:
        root = Path(ai_directory).resolve() if ai_directory else ai_root()
        path = root / "registry.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(LoadedRegistry(raw=raw, root=root))

    @classmethod
    def load_default(cls) -> Registry:
        return cls.load(None)

    @property
    def root(self) -> Path:
        return self._loaded.root

    @property
    def raw(self) -> dict:
        return self._loaded.raw

    def skill_path(self, skill_id: str) -> Path | None:
        info = self.raw.get("skills", {}).get(skill_id)
        if not info:
            return None
        rel = info.get("skillFile")
        if not rel:
            return None
        return self.root / rel

    def global_architecture_path(self) -> Path | None:
        routing = self.raw.get("routing") or {}
        rel = routing.get("globalSkillFile")
        if not rel:
            return None
        return self.root / rel

    def dependency_graph_path(self) -> Path | None:
        routing = self.raw.get("routing") or {}
        rel = routing.get("dependencyGraphFile")
        if not rel:
            return None
        return self.root / rel

    def module_skill_id(self, area: str) -> str | None:
        routing = self.raw.get("routing") or {}
        m = routing.get("moduleSkillId") or {}
        sid = m.get(area)
        return str(sid) if sid else None

    def keyword_routing(self) -> list[dict]:
        routing = self.raw.get("routing") or {}
        kr = routing.get("keywordRouting")
        return list(kr) if isinstance(kr, list) else []

    def skill_order(self) -> list[str]:
        return list(self.raw.get("skillOrder") or [])
