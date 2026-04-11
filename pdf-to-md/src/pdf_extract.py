"""PyMuPDF text/images, pdfplumber tables, optional OCR."""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz
import pdfplumber

from src.md_emit import table_to_markdown
from src.utils import ResolvedOutput, image_filename, markdown_link_to_image, resolve_output


@dataclass
class ConvertOptions:
    use_ocr: bool = False
    ocr_min_chars: int = 40
    verbose: bool = False


def _warn(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def _try_ocr_page(page: fitz.Page, verbose: bool) -> Optional[str]:
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        _warn(verbose, "pdf-to-md: --ocr requires pytesseract and Pillow (pip install pytesseract Pillow).")
        return None
    try:
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img)
        return text.strip() or None
    except Exception as e:
        _warn(verbose, f"pdf-to-md: OCR failed for a page: {e}")
        return None


def _collect_sizes_from_dict(page_dict: dict) -> List[float]:
    sizes: List[float] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                s = span.get("size")
                if isinstance(s, (int, float)) and s > 0:
                    sizes.append(float(s))
    return sizes


def _line_text_and_max_size(line: dict) -> Tuple[str, float]:
    parts: List[str] = []
    max_sz = 0.0
    for span in line.get("spans", []):
        parts.append(span.get("text", ""))
        s = span.get("size")
        if isinstance(s, (int, float)):
            max_sz = max(max_sz, float(s))
    return "".join(parts).strip(), max_sz


def _format_text_blocks(page: fitz.Page, _verbose: bool) -> Tuple[str, int]:
    """Return (markdown_fragment, plain_char_count)."""
    d = page.get_text("dict")
    blocks = [b for b in d.get("blocks", []) if b.get("type") == 0]
    blocks.sort(key=lambda b: (round(b["bbox"][1] / 5) * 5, b["bbox"][0]))

    sizes = _collect_sizes_from_dict(d)
    median_sz = statistics.median(sizes) if sizes else 10.0

    lines_out: List[str] = []
    plain_chars = 0
    for block in blocks:
        para_lines: List[str] = []
        for line in block.get("lines", []):
            text, max_sz = _line_text_and_max_size(line)
            if not text:
                continue
            plain_chars += len(text)
            is_heading = max_sz >= median_sz * 1.15 and max_sz >= median_sz + 1.5
            if is_heading:
                if para_lines:
                    lines_out.append(" ".join(para_lines))
                    para_lines = []
                lines_out.append(f"### {text}")
            else:
                para_lines.append(text)
        if para_lines:
            lines_out.append(" ".join(para_lines))
    body = "\n\n".join(lines_out).strip()
    return body, plain_chars


def _extract_page_images(
    doc: fitz.Document,
    page: fitz.Page,
    page_1based: int,
    images_dir: Path,
    markdown_path: Path,
    xref_to_dest: Dict[int, Path],
    next_image_index: List[int],
    verbose: bool,
) -> List[str]:
    links: List[str] = []
    page_xrefs: List[int] = []
    for info in page.get_images(full=True):
        xref = int(info[0])
        page_xrefs.append(xref)

    for xref in page_xrefs:
        if xref in xref_to_dest:
            dest = xref_to_dest[xref]
            rel = markdown_link_to_image(markdown_path, dest)
            links.append(f"![page {page_1based} image]({rel})")
            continue
        try:
            base = doc.extract_image(xref)
        except Exception as e:
            _warn(verbose, f"pdf-to-md: could not extract image xref={xref}: {e}")
            continue
        ext = (base.get("ext") or "png").lower()
        idx = next_image_index[0]
        next_image_index[0] = idx + 1
        name = image_filename(page_1based, idx, ext)
        dest = images_dir / name
        try:
            dest.write_bytes(base["image"])
        except Exception as e:
            _warn(verbose, f"pdf-to-md: could not write image {dest}: {e}")
            continue
        xref_to_dest[xref] = dest
        rel = markdown_link_to_image(markdown_path, dest)
        links.append(f"![page {page_1based} image]({rel})")
    return links


def _tables_for_page(plumber_page, verbose: bool) -> List[str]:
    parts: List[str] = []
    try:
        tables = plumber_page.find_tables() or []
        for t in tables:
            try:
                data = t.extract()
            except Exception as e:
                _warn(verbose, f"pdf-to-md: table extract failed: {e}")
                continue
            md = table_to_markdown(data)
            if md:
                parts.append(md)
    except Exception as e:
        _warn(verbose, f"pdf-to-md: pdfplumber find_tables failed: {e}")
    return parts


def convert_pdf(pdf_path: Path, resolved: ResolvedOutput, options: ConvertOptions) -> None:
    pdf_path = Path(pdf_path).resolve()
    md_path = Path(resolved.markdown_path)
    img_dir = Path(resolved.images_dir)
    img_dir.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    xref_to_dest: Dict[int, Path] = {}
    next_image_index: List[int] = [0]
    chunks: List[str] = []

    doc = fitz.open(pdf_path)
    try:
        plumber = pdfplumber.open(pdf_path)
        try:
            n_pages = min(len(doc), len(plumber.pages))
            for i in range(len(doc)):
                page = doc[i]
                page_n = i + 1
                chunks.append(f"## Page {page_n}")
                body, n_chars = _format_text_blocks(page, options.verbose)
                if options.use_ocr and n_chars < options.ocr_min_chars:
                    ocr_text = _try_ocr_page(page, options.verbose)
                    if ocr_text:
                        body = ocr_text
                if body:
                    chunks.append(body)

                img_links = _extract_page_images(
                    doc,
                    page,
                    page_n,
                    img_dir,
                    md_path,
                    xref_to_dest,
                    next_image_index,
                    options.verbose,
                )
                if img_links:
                    chunks.append("\n".join(img_links))

                if i < n_pages:
                    tbl_md = _tables_for_page(plumber.pages[i], options.verbose)
                    if tbl_md:
                        chunks.append("\n".join(tbl_md))
                chunks.append("")
        finally:
            plumber.close()
    finally:
        doc.close()

    md_path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8", newline="\n")


def convert_pdf_to_artifact_dir(
    pdf_path: Path,
    out_dir: Path,
    options: ConvertOptions,
) -> None:
    """Write OUTPUT/document.md and OUTPUT/assets/images/ (artifact bundle root)."""
    resolved = resolve_output(Path(out_dir), artifact_layout=True, images_dir=None)
    convert_pdf(Path(pdf_path), resolved, options)
