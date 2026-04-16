from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


def fetch_robots_parser(client: httpx.Client, page_url: str) -> RobotFileParser | None:
    """Load robots.txt for the origin of page_url; return None if missing or unreadable."""
    p = urlparse(page_url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r = client.get(robots_url, timeout=15.0)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(r.text.splitlines())
    return rp


async def fetch_robots_parser_async(
    client: httpx.AsyncClient, page_url: str
) -> RobotFileParser | None:
    """Async load of robots.txt for the origin of page_url."""
    p = urlparse(page_url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r = await client.get(robots_url, timeout=15.0)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(r.text.splitlines())
    return rp


def allowed_by_robots(
    rp: RobotFileParser | None,
    user_agent: str,
    url: str,
    *,
    obey: bool,
) -> bool:
    if not obey or rp is None:
        return True
    return rp.can_fetch(user_agent, url)
