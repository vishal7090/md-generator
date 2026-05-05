"""Go: JSON IR from ``FileParseResult.ir_dump`` → ``IRMethod`` list."""

from __future__ import annotations

from md_generator.codeflow.models.ir import FileParseResult
from md_generator.codeflow.parsers.adapters.ir_from_dump import ir_methods_from_dump_doc


def populate_ir_methods_go(fr: FileParseResult) -> None:
    doc = fr.ir_dump
    if not isinstance(doc, dict):
        fr.ir_methods = []
        return
    fp = str(fr.path.resolve())
    fr.ir_methods = ir_methods_from_dump_doc(doc, file_path=fp, language=fr.language or "go")
