"""Convert public HTTP(S) HTML pages to Markdown with downloaded assets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from md_generator.url.options import ConvertOptions

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ConvertOptions", "convert_url", "convert_urls_from_list"]


def __getattr__(name: str) -> object:
    if name == "convert_url":
        from md_generator.url.convert_impl import convert_url as v

        return v
    if name == "convert_urls_from_list":
        from md_generator.url.convert_impl import convert_urls_from_list as v

        return v
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
