from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from md_generator.playwright import assets, chunker, extractor, html_to_md


def test_extract_main_content_prefers_main() -> None:
    html = """<!DOCTYPE html><html><head></head><body>
    <nav>Nav</nav>
    <main><p>Hello main</p></main>
    <footer>Foot</footer>
    </body></html>"""
    out = extractor.extract_main_content(html)
    assert "Hello main" in out
    assert "Nav" not in out
    assert "Foot" not in out


def test_convert_html_to_markdown_headings() -> None:
    html = "<h2>Title</h2><ul><li>a</li></ul>"
    md = html_to_md.convert_html_to_markdown(html, use_readability=False)
    assert "## Title" in md or "Title" in md
    assert "a" in md


def test_chunk_markdown_inserts_markers() -> None:
    body = "\n\n".join([f"Paragraph {i} with some text." for i in range(80)])
    out = chunker.chunk_markdown(body, max_tokens=10, chars_per_token=4)
    assert "chunk:start" in out
    assert "chunk:end" in out


def test_process_assets_mock_transport(tmp_path: Path) -> None:
    img_url = "https://img.example.test/pixel.png"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "img.example.test":
            return httpx.Response(200, content=b"\x89PNG\r\n\x1a\n", headers={"content-type": "image/png"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    md = f"![x]({img_url})"
    out = assets.process_assets(
        md,
        "https://page.example.test/",
        tmp_path,
        client=client,
        max_images=5,
    )
    client.close()
    assert "assets/images/" in out
    imgs = list((tmp_path / "assets" / "images").glob("*"))
    assert len(imgs) >= 1
