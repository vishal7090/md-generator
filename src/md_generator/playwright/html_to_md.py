from __future__ import annotations

from markdownify import markdownify as html_to_markdown


def convert_html_to_markdown(html: str, *, use_readability: bool = True, page_url: str = "") -> str:
    """
    Optionally run readability on HTML fragment, then markdownify with sensible defaults.
    """
    fragment = html
    if use_readability:
        try:
            from readability import Document

            doc = Document(html, url=page_url or "https://example.com/")
            fragment = doc.summary()
        except Exception:
            fragment = html

    return html_to_markdown(
        fragment,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style", "noscript"],
    ).strip()
