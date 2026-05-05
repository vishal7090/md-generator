"""Fill ``FileParseResult.ir_methods`` when CFG export is enabled."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.adapters import (
    populate_ir_methods_java,
    populate_ir_methods_python,
)
from md_generator.codeflow.parsers.adapters.cpp_adapter import populate_ir_methods_cpp
from md_generator.codeflow.parsers.adapters.go_adapter import populate_ir_methods_go
from md_generator.codeflow.parsers.adapters.php_adapter import populate_ir_methods_php


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
        elif fr.language == "go" and cfg.cfg_ir_go:
            populate_ir_methods_go(fr)
        elif fr.language == "php" and cfg.cfg_ir_php:
            populate_ir_methods_php(fr)
        elif fr.language == "cpp" and cfg.cfg_ir_cpp:
            populate_ir_methods_cpp(fr, root)
        else:
            fr.ir_methods = []
