from __future__ import annotations

from src.options import ConvertOptions


def convert_options_from_query(
    *,
    include_source_block: bool = True,
    generate_toc: bool = False,
) -> ConvertOptions:
    """Map API query parameters to ConvertOptions (artifact layout forced at call site)."""
    return ConvertOptions(
        artifact_layout=True,
        include_source_block=include_source_block,
        generate_toc=generate_toc,
        verbose=False,
    )
