from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from md_generator.playwright.options import PlaywrightOptions
from md_generator.playwright.pipeline import convert_url_to_md


@pytest.mark.integration
def test_pipeline_react_tutorial(tmp_path: Path) -> None:
    opts = PlaywrightOptions(
        wait_until="load",
        navigation_timeout_ms=90_000.0,
        max_scroll_rounds=8,
        chunk_markdown=True,
    )
    out = tmp_path / "react"
    try:
        path = asyncio.run(
            convert_url_to_md(
                "https://react.dev/learn/tutorial-tic-tac-toe",
                out,
                opts,
            )
        )
    except Exception as e:
        msg = str(e).lower()
        if "executable doesn't exist" in msg or ("browser" in msg and "install" in msg):
            pytest.skip(f"Playwright browser missing: {e}")
        raise
    text = path.read_text(encoding="utf-8")
    assert "source: https://react.dev/learn/tutorial-tic-tac-toe" in text
    assert "React" in text or "react" in text.lower()
    assert "chunk:start" in text


@pytest.mark.integration
def test_pipeline_angular_overview(tmp_path: Path) -> None:
    opts = PlaywrightOptions(
        wait_until="load",
        navigation_timeout_ms=90_000.0,
        max_scroll_rounds=8,
        chunk_markdown=True,
    )
    out = tmp_path / "angular"
    try:
        path = asyncio.run(convert_url_to_md("https://angular.dev/overview", out, opts))
    except Exception as e:
        msg = str(e).lower()
        if "executable doesn't exist" in msg or ("browser" in msg and "install" in msg):
            pytest.skip(f"Playwright browser missing: {e}")
        raise
    text = path.read_text(encoding="utf-8")
    assert "angular.dev" in text
    assert "Angular" in text or "angular" in text.lower()
