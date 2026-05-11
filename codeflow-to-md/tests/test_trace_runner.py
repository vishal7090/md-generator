from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from md_generator.codeflow.graph.hotpath import normalize_runtime_trace


def test_trace_runner_cli_emits_normalized_edges(tmp_path: Path) -> None:
    script = tmp_path / "step.py"
    script.write_text(
        "x = 1\ny = 2\nz = x + y\n",
        encoding="utf-8",
    )
    mp = tmp_path / "map.json"
    mp.write_text(
        json.dumps(
            {
                "version": 1,
                "files": [
                    {
                        "path_suffix": "step.py",
                        "lines": {"1": "A", "2": "B", "3": "C"},
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    out = tmp_path / "trace.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "md_generator.codeflow.runtime.trace_runner",
            "-o",
            str(out),
            "--line-map",
            str(mp),
            str(script),
        ],
        check=True,
        cwd=tmp_path,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    norm = normalize_runtime_trace(data)
    assert norm.get("A->B", 0) >= 1.0
    assert norm.get("B->C", 0) >= 1.0
