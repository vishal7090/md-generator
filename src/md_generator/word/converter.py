from __future__ import annotations

import os
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import mammoth
from markdownify import markdownify as html_to_markdown

# Word built-ins and common variants → HTML (Mammoth style map)
_DEFAULT_STYLE_MAP = """
p[style-name='Heading 1'] => h1:fresh
p[style-name='Heading 2'] => h2:fresh
p[style-name='Heading 3'] => h3:fresh
p[style-name='Heading 4'] => h4:fresh
p[style-name='Heading 5'] => h5:fresh
p[style-name='Heading 6'] => h6:fresh
p[style-name='Title'] => h1.title:fresh
p[style-name='Subtitle'] => h2.subtitle:fresh
p[style-name='Quote'] => blockquote:fresh
p[style-name='Intense Quote'] => blockquote.intense:fresh
r[style-name='Strong'] => strong
r[style-name='Emphasis'] => em
"""


def _page_break_html_to_hr(html: str) -> str:
    """Map Mammoth / Word page-break-like breaks to <hr/> before markdownify."""
    html = re.sub(
        r"<br\s+[^>]*\bdata-mammoth-page-break\s*=\s*[\"']true[\"'][^>]*/?>",
        "<hr/>",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"<p\s+[^>]*\bdata-mammoth-page-break\s*=\s*[\"']true[\"'][^>]*>\s*</p>",
        "<hr/>",
        html,
        flags=re.IGNORECASE,
    )
    return html


def _extension_for_content_type(content_type: str) -> str:
    subtype = (content_type or "application/octet-stream").split("/")[-1].lower()
    if subtype in ("jpeg", "jpe"):
        return "jpg"
    if subtype in ("svg+xml",):
        return "svg"
    return subtype if subtype.isalnum() else "bin"


def _make_image_converter(images_dir: Path, rel_prefix: str):
    images_dir.mkdir(parents=True, exist_ok=True)

    def convert_image(image: mammoth.images.Image) -> dict[str, str]:
        ext = _extension_for_content_type(getattr(image, "content_type", "") or "")
        name = f"{uuid.uuid4().hex}.{ext}"
        dest = images_dir / name
        with image.open() as src:
            with dest.open("wb") as out:
                shutil.copyfileobj(src, out)
        rel = f"{rel_prefix}/{name}".replace("\\", "/")
        return {"src": rel}

    return convert_image


def _html_to_md(html: str) -> str:
    return html_to_markdown(
        html,
        heading_style="ATX",
        bullets="-",
        strip_document=None,
    ).strip() + "\n"


@dataclass
class ConversionResult:
    output_md: Path
    images_dir: Path
    markdown: str
    log_lines: list[str] = field(default_factory=list)


def convert_docx_to_markdown(
    input_docx: Path,
    output_md: Path,
    *,
    images_dir: Path | None = None,
    page_break_as_hr: bool = True,
    verbose: bool = False,
    conversion_log_path: Path | None = None,
    style_map: str | None = None,
) -> ConversionResult:
    """
    Convert .docx to Markdown next to ``images_dir``, optionally write conversion log.

    ``output_md`` parent directory is created as needed. Image paths in Markdown are
    relative to ``output_md``'s parent (e.g. ``images/<id>.png``).
    """
    input_docx = Path(input_docx)
    output_md = Path(output_md)
    if images_dir is None:
        images_dir = output_md.parent / "images"
    else:
        images_dir = Path(images_dir)

    output_md.parent.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    out_parent = output_md.parent.resolve()
    img_abs = images_dir.resolve()
    rel_prefix_posix = os.path.relpath(img_abs, out_parent).replace("\\", "/")

    convert_image = _make_image_converter(images_dir, rel_prefix_posix)
    sm = style_map if style_map is not None else _DEFAULT_STYLE_MAP

    with input_docx.open("rb") as docx_file:
        result = mammoth.convert_to_html(
            docx_file,
            style_map=sm,
            convert_image=mammoth.images.img_element(convert_image),
        )

    html = result.value
    log_lines = [str(m) for m in result.messages]

    if verbose:
        for line in log_lines:
            print(line, file=sys.stderr)

    if page_break_as_hr:
        html = _page_break_html_to_hr(html)

    markdown = _html_to_md(html)
    output_md.write_text(markdown, encoding="utf-8")

    if conversion_log_path is not None:
        conversion_log_path = Path(conversion_log_path)
        conversion_log_path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(log_lines) if log_lines else "(no Mammoth messages)\n"
        conversion_log_path.write_text(body, encoding="utf-8")

    return ConversionResult(
        output_md=output_md,
        images_dir=images_dir,
        markdown=markdown,
        log_lines=log_lines,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Convert .docx to Markdown.")
    parser.add_argument("input_docx", type=Path, help="Input .docx path")
    parser.add_argument("output_md", type=Path, help="Output .md path")
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Directory for extracted images (default: <parent of output>/images)",
    )
    parser.add_argument(
        "--no-page-break-hr",
        action="store_true",
        help="Do not map page-break-like spans to horizontal rules",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        convert_docx_to_markdown(
            args.input_docx,
            args.output_md,
            images_dir=args.images_dir,
            page_break_as_hr=not args.no_page_break_hr,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
