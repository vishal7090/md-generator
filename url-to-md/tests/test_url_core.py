from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from md_generator.url.extract import extract_same_site_links, normalize_url, same_site
from md_generator.url.options import ConvertOptions
from md_generator.url.page_convert import convert_one_page_artifact


@pytest.fixture()
def noop_client() -> httpx.Client:
    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    return httpx.Client(transport=transport)


def test_same_site_subdomain() -> None:
    assert same_site(
        "https://a.example.com/p",
        "https://b.example.com/q",
        include_subdomains=True,
    ) is False
    assert same_site(
        "https://sub.example.com/",
        "https://example.com/",
        include_subdomains=True,
    ) is True


def test_extract_same_site_links() -> None:
    html = """
    <html><body>
    <a href="/rel">rel</a>
    <a href="https://other.com/x">ext</a>
    <a href="https://example.com/other">same</a>
    </body></html>
    """
    links = extract_same_site_links(html, "https://example.com/start", include_subdomains=True)
    assert "https://example.com/rel" in links
    assert "https://example.com/other" in links
    assert not any("other.com" in u for u in links)


def test_convert_one_page_artifact_minimal(tmp_path: Path, noop_client: httpx.Client) -> None:
    html = """<!DOCTYPE html>
<html><head><title>Fixture</title></head><body>
<article><h1>Hello</h1><p>Paragraph text.</p>
<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
</article></body></html>"""
    out = tmp_path / "art"
    opts = ConvertOptions(artifact_layout=True, table_csv=True)
    convert_one_page_artifact("https://example.com/doc", html, out, opts, noop_client)
    doc = (out / "document.md").read_text(encoding="utf-8")
    assert "Hello" in doc or "Fixture" in doc
    assert "Paragraph" in doc
    tables = list((out / "assets" / "tables").glob("*.csv"))
    assert tables


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://a.com/x#y") == "https://a.com/x"
