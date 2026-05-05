from __future__ import annotations

from pathlib import Path


def find_tools_dir(name: str) -> Path | None:
    """Locate ``tools/<name>/`` or ``codeflow-to-md/examples/<name>/`` by walking up from this package."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        for rel in ("tools", Path("codeflow-to-md") / "examples"):
            cand = anc / rel / name
            if not cand.is_dir():
                continue
            if (cand / "main.go").is_file() or (cand / "dump.php").is_file():
                return cand
    return None
