from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from md_generator.log.utils.io import write_text


def write_run_metadata(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, default=str) + "\n")
