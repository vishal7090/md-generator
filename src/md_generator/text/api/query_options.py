from __future__ import annotations

from md_generator.text.options import ConvertOptions, StructureMode, XmlParser


def convert_options_from_query(
    *,
    include_source_block: bool = True,
    generate_toc: bool = False,
    structure: StructureMode = "hierarchical",
    xml_parser: XmlParser = "auto",
) -> ConvertOptions:
    """Map API query parameters to ConvertOptions (artifact layout forced at call site)."""
    return ConvertOptions(
        artifact_layout=True,
        include_source_block=include_source_block,
        generate_toc=generate_toc,
        verbose=False,
        structure=structure,
        xml_parser=xml_parser,
    )
