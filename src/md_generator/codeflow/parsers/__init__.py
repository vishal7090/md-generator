from __future__ import annotations

from md_generator.codeflow.parsers.base import ParserRegistry, register_defaults
from md_generator.codeflow.parsers.cpp_parser import CppParser
from md_generator.codeflow.parsers.go_parser import GoParser
from md_generator.codeflow.parsers.java_parser import JavaParser
from md_generator.codeflow.parsers.php_parser import PhpParser
from md_generator.codeflow.parsers.python_parser import PythonParser

__all__ = [
    "ParserRegistry",
    "register_defaults",
    "CppParser",
    "GoParser",
    "JavaParser",
    "PhpParser",
    "PythonParser",
]
