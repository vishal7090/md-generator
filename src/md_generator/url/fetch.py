from __future__ import annotations

from dataclasses import dataclass

import httpx

from md_generator.url.options import ConvertOptions


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str | None
    text: str


def _is_probably_html(content_type: str | None, text: str) -> bool:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in ("text/html", "application/xhtml+xml"):
            return True
        if "html" in ct:
            return True
    sample = text[:500].lstrip().lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html")


def fetch_html(url: str, client: httpx.Client, options: ConvertOptions) -> FetchResult:
    """GET URL and return decoded text, enforcing a response size cap while streaming."""
    max_b = options.max_response_bytes
    total = 0
    chunks: list[bytes] = []
    ct: str | None = None
    with client.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=options.timeout_seconds,
    ) as resp:
        resp.raise_for_status()
        ct = resp.headers.get("content-type")
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > max_b:
                raise ValueError(
                    f"Response exceeds max_response_bytes ({max_b} bytes); "
                    "raise limit or use a smaller page."
                )
            chunks.append(chunk)
        final_url = str(resp.url)
        status_code = resp.status_code
        encoding = resp.encoding or "utf-8"

    raw = b"".join(chunks)
    text = raw.decode(encoding, errors="replace")
    if not _is_probably_html(ct, text):
        raise ValueError(
            f"URL did not return HTML (content-type={ct!r}). "
            "Only text/html responses are supported in v1."
        )
    return FetchResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        content_type=ct,
        text=text,
    )


def new_client(options: ConvertOptions) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": options.user_agent},
        follow_redirects=True,
        timeout=options.timeout_seconds,
    )


async def fetch_html_async(
    url: str, client: httpx.AsyncClient, options: ConvertOptions
) -> FetchResult:
    """Async GET with the same size cap and HTML checks as fetch_html."""
    max_b = options.max_response_bytes
    total = 0
    chunks: list[bytes] = []
    ct: str | None = None
    async with client.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=options.timeout_seconds,
    ) as resp:
        resp.raise_for_status()
        ct = resp.headers.get("content-type")
        async for chunk in resp.aiter_bytes():
            total += len(chunk)
            if total > max_b:
                raise ValueError(
                    f"Response exceeds max_response_bytes ({max_b} bytes); "
                    "raise limit or use a smaller page."
                )
            chunks.append(chunk)
        final_url = str(resp.url)
        status_code = resp.status_code
        encoding = resp.encoding or "utf-8"

    raw = b"".join(chunks)
    text = raw.decode(encoding, errors="replace")
    if not _is_probably_html(ct, text):
        raise ValueError(
            f"URL did not return HTML (content-type={ct!r}). "
            "Only text/html responses are supported in v1."
        )
    return FetchResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        content_type=ct,
        text=text,
    )


def new_async_client(options: ConvertOptions) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": options.user_agent},
        follow_redirects=True,
        timeout=options.timeout_seconds,
    )
