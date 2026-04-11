from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from src.format_detect import detect_format
from src.md_emit_json import json_to_markdown
from src.md_emit_txt import txt_to_markdown
from src.md_emit_xml import xml_to_markdown
from src.options import ConvertOptions

ALLOWED_SUFFIXES = {".txt", ".json", ".xml"}
ARTIFACT_MD_NAME = "document.md"


def _decode_text(raw: bytes, encoding: str) -> str:
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to decode file as {encoding!r}: {e}") from e


def convert_text_file(input_path: Path, output: Path, options: ConvertOptions) -> None:
    input_path = Path(input_path)
    output = Path(output)
    suf = input_path.suffix.lower()
    if suf not in ALLOWED_SUFFIXES:
        raise ValueError(f"Input must be .txt, .json, or .xml (got {input_path.suffix!r})")

    raw = input_path.read_bytes()
    text = _decode_text(raw, options.encoding)
    if text.startswith("\ufeff"):
        text = text[1:]

    fmt = detect_format(input_path, text, options.input_format)

    if fmt == "json":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        md = json_to_markdown(
            obj,
            text,
            include_source_block=options.include_source_block,
            generate_toc=options.generate_toc,
        )
    elif fmt == "xml":
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}") from e
        md = xml_to_markdown(
            root,
            text,
            include_source_block=options.include_source_block,
            generate_toc=options.generate_toc,
        )
    else:
        md = txt_to_markdown(text)

    if options.verbose:
        print(f"Detected format: {fmt}", file=sys.stderr)

    if options.artifact_layout:
        output.mkdir(parents=True, exist_ok=True)
        (output / ARTIFACT_MD_NAME).write_text(md, encoding="utf-8", newline="\n")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md, encoding="utf-8", newline="\n")
