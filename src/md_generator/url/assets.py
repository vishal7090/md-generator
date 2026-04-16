from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from md_generator.url.options import ConvertOptions


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


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name)[:100] or "file"


def download_binary_limited(
    client: httpx.Client,
    url: str,
    max_bytes: int,
    timeout: float,
) -> tuple[bytes, str | None]:
    total = 0
    chunks: list[bytes] = []
    ct: str | None = None
    with client.stream("GET", url, follow_redirects=True, timeout=timeout) as resp:
        resp.raise_for_status()
        ct = resp.headers.get("content-type")
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Asset exceeds max_response_bytes when fetching {url!r}")
            chunks.append(chunk)
    return b"".join(chunks), ct


def collect_and_download_assets(
    full_html: str,
    page_url: str,
    *,
    output_dir: Path,
    images_rel: Path,
    files_rel: Path,
    client: httpx.Client,
    options: ConvertOptions,
    max_images: int | None = None,
    max_files: int | None = None,
) -> dict[str, str]:
    """
    Download <img src> and selected <a href> targets.
    Returns map absolute URL (normalized) -> path relative to output_dir (posix).
    """
    max_img = max_images if max_images is not None else options.max_downloaded_images
    max_f = max_files if max_files is not None else options.max_linked_files

    soup = BeautifulSoup(full_html, "lxml")
    url_map: dict[str, str] = {}
    seen_target: set[str] = set()

    img_dir = output_dir / images_rel
    file_dir = output_dir / files_rel
    img_dir.mkdir(parents=True, exist_ok=True)
    if options.download_linked_files:
        file_dir.mkdir(parents=True, exist_ok=True)

    img_count = 0
    for img in soup.find_all("img", src=True):
        if img_count >= max_img:
            break
        src = str(img.get("src", "")).strip()
        if not src or src.startswith("data:"):
            continue
        abs_u = urljoin(page_url, src)
        if abs_u in seen_target:
            continue
        seen_target.add(abs_u)
        try:
            data, ct = download_binary_limited(
                client,
                abs_u,
                options.max_response_bytes,
                options.timeout_seconds,
            )
        except Exception:
            continue
        ext = _guess_ext(abs_u, ct)
        fname = f"img_{img_count + 1:03d}_{_short_hash(abs_u)}{ext}"
        fname = _safe_name(fname)
        rel_path = images_rel / fname
        path = output_dir / rel_path
        path.write_bytes(data)
        url_map[_normalize_url(abs_u)] = rel_path.as_posix()
        img_count += 1

    file_count = 0
    if options.download_linked_files:
        exts = tuple(e.lower() for e in options.linked_file_extensions)
        for a in soup.find_all("a", href=True):
            if file_count >= max_f:
                break
            href = str(a.get("href", "")).strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_u = urljoin(page_url, href)
            low = abs_u.lower()
            path_only = low.split("?", 1)[0]
            if not any(path_only.endswith(ext) for ext in exts):
                continue
            if abs_u in seen_target:
                continue
            seen_target.add(abs_u)
            try:
                data, ct = download_binary_limited(
                    client,
                    abs_u,
                    options.max_response_bytes,
                    options.timeout_seconds,
                )
            except Exception:
                continue
            ext = _guess_ext(abs_u, ct)
            fname = f"file_{file_count + 1:03d}_{_short_hash(abs_u)}{ext}"
            fname = _safe_name(fname)
            rel_path = files_rel / fname
            path = output_dir / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            url_map[_normalize_url(abs_u)] = rel_path.as_posix()
            file_count += 1

    return url_map


def _normalize_url(u: str) -> str:
    p = urlparse(u)
    return urlunparse(p._replace(fragment=""))


def rewrite_markdown_urls(md: str, url_map: dict[str, str]) -> str:
    out = md
    for abs_u, rel in sorted(url_map.items(), key=lambda x: -len(x[0])):
        out = out.replace(abs_u, rel)
        if abs_u.startswith("https://"):
            alt = "http://" + abs_u[len("https://") :]
            out = out.replace(alt, rel)
        elif abs_u.startswith("http://"):
            alt = "https://" + abs_u[len("http://") :]
            out = out.replace(alt, rel)
    return out
