"""Fill ``FileParseResult.ir_methods`` when CFG export is enabled."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.adapters import (
    populate_ir_methods_java,
    populate_ir_methods_python,
)


def enrich_parse_results_with_ir(results: list[FileParseResult], cfg: ScanConfig, project_root: Path) -> None:
    if not cfg.emit_cfg:
        return
    root = project_root.resolve()
    for fr in results:
        if fr.language == "python":
            populate_ir_methods_python(fr, root)
        elif fr.language == "java":
            populate_ir_methods_java(fr, root)
        elif fr.language in ("javascript", "typescript", "tsx"):
            try:
                from md_generator.codeflow.parsers.adapters import populate_ir_methods_treesitter

                populate_ir_methods_treesitter(fr, root)
            except ImportError:
                fr.ir_methods = []
        else:
            fr.ir_methods = []
