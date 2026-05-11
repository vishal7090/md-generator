from __future__ import annotations

import json
import sys
from pathlib import Path

from md_generator.text.format_detect import detect_format
from md_generator.text.md_emit_json import json_to_markdown
from md_generator.text.md_emit_txt import txt_to_markdown
from md_generator.text.md_emit_xml import xml_to_markdown
from md_generator.text.md_flatten import json_flatten_to_markdown, xml_flatten_to_markdown
from md_generator.text.options import ConvertOptions
from md_generator.text.xml_parse import parse_xml_root

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
        if options.structure == "flattened":
            md = json_flatten_to_markdown(
                obj,
                text,
                include_source_block=options.include_source_block,
                generate_toc=options.generate_toc,
            )
        else:
            md = json_to_markdown(
                obj,
                text,
                include_source_block=options.include_source_block,
                generate_toc=options.generate_toc,
            )
    elif fmt == "xml":
        if options.structure == "flattened":
            try:
                md = xml_flatten_to_markdown(
                    text,
                    text,
                    include_source_block=options.include_source_block,
                    generate_toc=options.generate_toc,
                )
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Invalid XML (flattened parse): {e}") from e
        else:
            try:
                root = parse_xml_root(text, options.xml_parser)
            except ValueError:
                raise
            except Exception as e:
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
