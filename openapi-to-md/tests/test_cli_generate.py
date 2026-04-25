from __future__ import annotations

from pathlib import Path

from md_generator.openapi.cli.main import main

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_openapi.yaml"


def test_cli_generate_smoke(tmp_path: Path) -> None:
    rc = main(
        [
            "generate",
            "--file",
            str(_FIXTURE),
            "--output",
            str(tmp_path),
            "--formats",
            "md,mermaid",
        ]
    )
    assert rc == 0
    assert (tmp_path / "README.md").is_file()
