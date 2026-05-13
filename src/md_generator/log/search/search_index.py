from __future__ import annotations

import json
from pathlib import Path


def load_index(index_root: Path) -> list[dict[str, object]]:
    manifest = index_root / "chunks" / "manifest.json"
    if not manifest.is_file():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []
