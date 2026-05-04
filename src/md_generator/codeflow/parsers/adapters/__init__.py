"""Language adapters: native AST / tree-sitter → normalized IR."""

from md_generator.codeflow.parsers.adapters.java_adapter import populate_ir_methods_java
from md_generator.codeflow.parsers.adapters.python_adapter import populate_ir_methods_python

__all__ = ["populate_ir_methods_python", "populate_ir_methods_java"]


def populate_ir_methods_treesitter(fr, project_root):  # type: ignore[no-untyped-def]
    """Populate IR for JS/TS/TSX when tree-sitter extras are installed."""
    from md_generator.codeflow.parsers.adapters.treesitter_adapter import populate_ir_methods_treesitter as impl

    return impl(fr, project_root)
