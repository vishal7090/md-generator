from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class Checkpoint:
    path: str
    offset: int = 0
    inode: int | None = None
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


def load_checkpoint(path: Path) -> Checkpoint | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Checkpoint(
            path=str(data.get("path", "")),
            offset=int(data.get("offset", 0)),
            inode=data.get("inode"),
            updated_at=str(data.get("updated_at", "")),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def save_checkpoint(path: Path, cp: Checkpoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cp.touch()
    path.write_text(json.dumps(asdict(cp), indent=2), encoding="utf-8")
