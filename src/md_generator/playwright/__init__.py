"""Playwright-based SPA render → Markdown pipeline."""

from md_generator.playwright.options import PlaywrightOptions
from md_generator.playwright.pipeline import convert_url_to_md

__all__ = ["PlaywrightOptions", "convert_url_to_md"]
