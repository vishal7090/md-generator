from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


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
