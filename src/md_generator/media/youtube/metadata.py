"""Fetch YouTube page metadata via HTTP + BeautifulSoup, with oEmbed fallback."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)


class YouTubeMetadataError(RuntimeError):
    """Raised when metadata cannot be fetched or parsed."""


def _host_ok(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower()
    if h in _YOUTUBE_HOSTS:
        return True
    return h.endswith(".youtube.com")


def extract_video_id(url: str) -> str | None:
    """Return 11-character video id or ``None`` if ``url`` is not a recognized YouTube URL."""
    raw = (url or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not _host_ok(host):
        return None
    path = parsed.path or ""
    vid_re = re.compile(r"^[\w-]{11}$")

    if host in ("youtu.be", "www.youtu.be"):
        seg = path.strip("/").split("/")[0] if path else ""
        return seg if vid_re.match(seg) else None

    if path.startswith("/watch"):
        v = (parse_qs(parsed.query).get("v") or [None])[0]
        return v if v and vid_re.match(v) else None
    if path.startswith("/embed/"):
        seg = path[len("/embed/") :].split("/")[0]
        return seg if vid_re.match(seg) else None
    if path.startswith("/shorts/"):
        seg = path[len("/shorts/") :].split("/")[0]
        return seg if vid_re.match(seg) else None
    if path.startswith("/live/"):
        seg = path[len("/live/") :].split("/")[0]
        return seg if vid_re.match(seg) else None
    return None


def normalize_youtube_url(url: str) -> str:
    """Return canonical ``https`` watch URL for a valid YouTube input."""
    vid = extract_video_id(url)
    if not vid:
        raise YouTubeMetadataError(f"Not a recognized YouTube URL: {url!r}")
    return f"https://www.youtube.com/watch?v={vid}"


def _parse_iso8601_duration(s: str) -> float | None:
    """Parse ``PT#H#M#S`` into seconds (best-effort)."""
    s = (s or "").strip()
    m = re.match(
        r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    h, mi, se = m.group(1), m.group(2), m.group(3)
    total = 0.0
    if h:
        total += int(h) * 3600
    if mi:
        total += int(mi) * 60
    if se:
        total += float(se)
    return total if total > 0 or (h or mi or se) else None


def _parse_views(content: str | None) -> int | None:
    if not content:
        return None
    digits = re.sub(r"[^\d]", "", str(content))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_meta_from_html(html: str) -> dict[str, Any]:
    """Parse watch-page HTML; fields may be missing (YouTube serves varying static HTML)."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, Any] = {
        "title": None,
        "description": None,
        "views": None,
        "keywords": None,
        "duration_seconds": None,
    }

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        out["title"] = str(og_title["content"]).strip()

    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        out["description"] = str(og_desc["content"]).strip()

    for meta in soup.find_all("meta"):
        prop = (meta.get("itemprop") or "").lower()
        name = (meta.get("name") or "").lower()
        content = meta.get("content")
        if prop == "interactioncount" or name == "interactioncount":
            out["views"] = out["views"] or _parse_views(content)
        if prop == "duration" and content:
            dur = _parse_iso8601_duration(str(content))
            if dur is not None:
                out["duration_seconds"] = dur
        if name == "keywords" and content:
            out["keywords"] = str(content).strip()

    return out


def _fetch_oembed(watch_url: str, *, client: httpx.Client) -> dict[str, Any]:
    params = {"url": watch_url, "format": "json"}
    r = client.get("https://www.youtube.com/oembed", params=params, timeout=30.0)
    r.raise_for_status()
    return r.json()


def fetch_youtube_metadata(
    video_id: str,
    page_url: str | None = None,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """
    Return metadata dict: title, description, views, keywords, duration_seconds, author, url.

    Uses watch-page HTML (BeautifulSoup) plus oEmbed JSON as fallback for title/author.
    Missing fields are omitted or ``None`` (never fabricated).
    """
    watch = page_url or f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    close = client is None
    c = client or httpx.Client(headers=headers, follow_redirects=True)
    try:
        merged: dict[str, Any] = {
            "video_id": video_id,
            "url": watch,
            "title": None,
            "description": None,
            "views": None,
            "keywords": None,
            "duration_seconds": None,
            "author": None,
        }
        try:
            r = c.get(watch, timeout=30.0)
            if r.status_code == 200 and r.text:
                html_meta = _parse_meta_from_html(r.text)
                for k in ("title", "description", "views", "keywords", "duration_seconds"):
                    if html_meta.get(k) is not None:
                        merged[k] = html_meta[k]
        except httpx.HTTPError:
            pass

        try:
            oj = _fetch_oembed(watch, client=c)
            if not merged.get("title") and oj.get("title"):
                merged["title"] = str(oj["title"]).strip()
            if oj.get("author_name"):
                merged["author"] = str(oj["author_name"]).strip()
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            pass

        return merged
    finally:
        if close:
            c.close()
