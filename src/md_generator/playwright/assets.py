from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx

_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _short_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _guess_ext(url: str, content_type: str | None) -> str:
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if "png" in ct:
            return ".png"
        if "jpeg" in ct or "jpg" in ct:
            return ".jpg"
        if "gif" in ct:
            return ".gif"
        if "webp" in ct:
            return ".webp"
        if "svg" in ct:
            return ".svg"
    return ".bin"


def _download_image(
    client: httpx.Client,
    abs_url: str,
    max_bytes: int,
    timeout: float,
) -> tuple[bytes, str | None]:
    total = 0
    chunks: list[bytes] = []
    ct: str | None = None
    with client.stream("GET", abs_url, follow_redirects=True, timeout=timeout) as resp:
        resp.raise_for_status()
        ct = resp.headers.get("content-type")
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Image exceeds max_image_bytes when fetching {abs_url!r}")
            chunks.append(chunk)
    return b"".join(chunks), ct


def process_assets(
    markdown: str,
    base_url: str,
    output_dir: Path | str,
    *,
    client: httpx.Client | None = None,
    max_images: int = 40,
    max_image_bytes: int = 5 * 1024 * 1024,
    asset_timeout_seconds: float = 30.0,
    url_filter: Callable[[str], bool] | None = None,
) -> str:
    """
    Find Markdown image references, download http(s) targets under output_dir/assets/images,
    rewrite to relative paths. Optional ``client`` for tests; optional ``url_filter`` to limit URLs.
    """
    out = Path(output_dir)
    img_dir = out / "assets" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    own_client = client is None
    hc = client or httpx.Client(
        headers={"User-Agent": "mdengine-playwright/0.1"},
        follow_redirects=True,
    )
    try:
        result = markdown
        seen = 0
        for m in _MD_IMG.finditer(markdown):
            if seen >= max_images:
                break
            alt, raw = m.group(1), m.group(2).strip()
            if raw.startswith("data:"):
                continue
            if raw.startswith(("http://", "https://")):
                abs_url = raw
            else:
                abs_url = urljoin(base_url, raw)
            if not abs_url.startswith(("http://", "https://")):
                continue
            if url_filter is not None and not url_filter(abs_url):
                continue
            try:
                data, ct = _download_image(
                    hc,
                    abs_url,
                    max_image_bytes,
                    asset_timeout_seconds,
                )
                ext = _guess_ext(abs_url, ct)
                name = f"img_{seen + 1:03d}_{_short_hash(abs_url)}{ext}"
                dest = img_dir / name
                dest.write_bytes(data)
                rel = f"assets/images/{name}"
                new_ref = f"![{alt}]({rel})"
                result = result.replace(m.group(0), new_ref, 1)
                seen += 1
            except Exception:
                continue
        return result
    finally:
        if own_client:
            hc.close()
