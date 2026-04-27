from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


RuleSource = Literal["branch", "validation", "sql_trigger", "predicate"]
RuleConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True, slots=True)
class BusinessRule:
    """Extracted business-oriented rule for documentation (not evaluated at runtime)."""

    source: RuleSource
    symbol_id: str | None
    file_path: str
    line: int
    title: str
    detail: str
    confidence: RuleConfidence = "medium"


class EntryKind(str, Enum):
    API_REST = "api_rest"
    MAIN = "main"
    CLI = "cli"
    SCHEDULER = "scheduler"
    KAFKA = "kafka"
    QUEUE = "queue"
    UNKNOWN = "unknown"


CallResolution = Literal["static", "dynamic", "unknown"]


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """Language-agnostic reference to a callable."""

    module_path: str
    class_name: str | None
    method_name: str
    file_path: str
    language: str

    def stable_id(self, project_root: Path) -> str:
        try:
            rel = Path(self.file_path).resolve().relative_to(project_root.resolve())
            key = rel.as_posix()
        except ValueError:
            key = Path(self.file_path).as_posix()
        if self.class_name:
            return f"{key}::{self.class_name}.{self.method_name}"
        return f"{key}::{self.method_name}"


@dataclass(slots=True)
class CallSite:
    caller_id: str
    callee_hint: str
    resolution: CallResolution
    is_async: bool
    line: int
    condition_label: str | None = None


@dataclass(slots=True)
class BranchPoint:
    caller_id: str
    kind: Literal["if", "else", "elif", "switch", "loop"]
    label: str | None
    line: int


@dataclass(slots=True)
class EntryRecord:
    """Detected entry point (API handler, main, etc.)."""

    symbol_id: str
    kind: EntryKind
    label: str
    file_path: str
    line: int


@dataclass
class FileParseResult:
    path: Path
    language: str
    symbol_ids: list[str] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    branches: list[BranchPoint] = field(default_factory=list)
    entries: list[EntryRecord] = field(default_factory=list)
    rules: list[BusinessRule] = field(default_factory=list)
