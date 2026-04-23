from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def try_resolve_dot_executable() -> str | None:
    env = os.environ.get("GRAPHVIZ_DOT")
    if env:
        p = Path(env)
        if p.is_file():
            return str(p.resolve())
    return shutil.which("dot")


def resolve_dot_executable() -> str:
    w = try_resolve_dot_executable()
    if not w:
        raise RuntimeError(
            "Graphviz executable 'dot' not found. Install Graphviz and add it to PATH, "
            "or set GRAPHVIZ_DOT to the full path of dot."
        )
    return w


def render_dot_to(dot_exe: str, dot_path: Path, out_path: Path, fmt: str) -> None:
    """Run `dot -T{fmt}` producing out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [dot_exe, f"-T{fmt}", "-o", str(out_path), str(dot_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"Graphviz failed ({fmt}): {err or r.returncode}")
