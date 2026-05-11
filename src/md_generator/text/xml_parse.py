from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def parse_xml_root(xml_text: str, xml_parser: str) -> Any:
    """Return an Element-like root (stdlib or lxml)."""
    if xml_parser == "stdlib":
        return ET.fromstring(xml_text)

    if xml_parser == "lxml":
        try:
            from lxml import etree
        except ImportError as e:
            raise ValueError(
                "xml_parser=lxml requires lxml. Install: pip install 'mdengine[text]' (or pip install lxml)."
            ) from e
        return etree.fromstring(
            xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
        )

    # auto
    try:
        from lxml import etree

        return etree.fromstring(
            xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text
        )
    except ImportError:
        return ET.fromstring(xml_text)
