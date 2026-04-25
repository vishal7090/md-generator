from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_SQLITE_MAGIC = b"SQLite format 3\x00"


def is_sqlite_database_bytes(data: bytes) -> bool:
    return len(data) >= len(_SQLITE_MAGIC) and data[: len(_SQLITE_MAGIC)] == _SQLITE_MAGIC


def sqlite_uri_for_path(abs_path: Path) -> str:
    """Build a SQLAlchemy SQLite URI for an absolute filesystem path."""
    return f"sqlite:///{abs_path.resolve().as_posix()}"


def redact_uri(uri: str) -> str:
    """Mask password in URI for logs and README."""
    try:
        p = urlparse(uri)
        if p.password is not None:
            netloc = p.hostname or ""
            if p.port:
                netloc += f":{p.port}"
            if p.username:
                netloc = f"{p.username}:***@{netloc}"
            else:
                netloc = f"***@{netloc}"
            return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
    except Exception:
        pass
    return re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1***\3", uri, count=1)
