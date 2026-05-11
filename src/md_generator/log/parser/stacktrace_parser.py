from __future__ import annotations

import re

_ST_AT = re.compile(r"^\s+at\s+[\w$.]+\([^)]*\)\s*(~\[.*\])?\s*$")
_ST_CAUSED = re.compile(r"^\s*Caused by:\s*")
_EXC_LINE = re.compile(
    r"^[a-zA-Z][\w.$]*(?:Exception|Error)(?::\s*|\s*$)",
)


def is_stacktrace_line(line: str) -> bool:
    s = line.rstrip("\n\r")
    if not s.strip():
        return False
    t = s.lstrip()
    if t.startswith("at ") or t.startswith("\tat "):
        return True
    if _ST_AT.match(s):
        return True
    if _ST_CAUSED.match(s):
        return True
    if s.startswith("java.lang.") or ".reflect." in s:
        return True
    if _EXC_LINE.match(s.strip()):
        return True
    if s.startswith("... ") and " more" in s:
        return True
    return False
