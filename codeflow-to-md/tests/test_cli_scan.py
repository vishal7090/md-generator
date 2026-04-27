from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_scan_mini_python(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "mini_python"
    out = tmp_path / "out"
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    r = subprocess.run(
        [sys.executable, "-m", "md_generator.codeflow.cli.main", "scan", str(root), "--output", str(out), "--depth", "3"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    graph = out / "graph-full.json"
    assert graph.is_file()
    assert graph.read_text(encoding="utf-8").strip().startswith("{")
