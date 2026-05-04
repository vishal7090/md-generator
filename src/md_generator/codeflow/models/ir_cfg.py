"""Language-agnostic control-flow IR (no AST imports here)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

IRStmtKind = Literal[
    "IF",
    "LOOP",
    "SWITCH",
    "TRY",
    "CALL",
    "RETURN",
    "STATEMENT",
]


@dataclass(frozen=True, slots=True)
class IRStmt:
    kind: IRStmtKind
    condition: str | None = None
    body: tuple["IRStmt", ...] = ()
    else_body: tuple["IRStmt", ...] = ()
    # Switch: (case_label, stmts); Try: ("except:Type", stmts) or ("finally", stmts)
    cases: tuple[tuple[str, tuple["IRStmt", ...]], ...] = ()
    target: str | None = None
    label: str | None = None
    line: int | None = None


@dataclass(frozen=True, slots=True)
class IRMethod:
    """One callable body in normalized IR."""

    symbol_id: str
    name: str
    file_path: str
    language: str
    body: tuple[IRStmt, ...] = ()
