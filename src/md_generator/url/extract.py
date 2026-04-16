from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """Drop fragment; trim whitespace."""
    u = url.strip()
    u, _frag = urldefrag(u)
    return u


def same_site(url_a: str, url_b: str, *, include_subdomains: bool) -> bool:
    pa, pb = urlparse(url_a), urlparse(url_b)
    if pa.scheme.lower() != pb.scheme.lower():
        return False
    ha, hb = pa.netloc.lower(), pb.netloc.lower()
    if ha == hb:
        return True
    if not include_subdomains:
        return False
    if ha.endswith("." + hb) or hb.endswith("." + ha):
        return True
    return False


def extract_same_site_links(html: str, base_url: str, *, include_subdomains: bool) -> list[str]:
    """Collect absolute HTTP(S) links in the same site as base_url."""
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    seen: set[str] = set()
    base_n = normalize_url(base_url)
    for a in soup.find_all("a", href=True):
        raw = a.get("href", "").strip()
        if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        abs_u = normalize_url(urljoin(base_n, raw))
        p = urlparse(abs_u)
        if p.scheme not in ("http", "https"):
            continue
        if not same_site(base_n, abs_u, include_subdomains=include_subdomains):
            continue
        if abs_u in seen:
            continue
        seen.add(abs_u)
        out.append(abs_u)
    return out


def extract_title_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        return t or None
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    return None


def url_to_slug(url: str, index: int) -> str:
    p = urlparse(url)
    path = (p.path or "/").strip("/").replace("/", "_") or "index"
    host = p.netloc.replace(":", "_")
    raw = f"{index:04d}_{host}_{path}"
    raw = re.sub(r"[^\w.\-]+", "_", raw)
    return raw[:140] if len(raw) > 140 else raw
