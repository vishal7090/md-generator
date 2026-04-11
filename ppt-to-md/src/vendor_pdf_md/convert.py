from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber


def pdf_to_markdown(
    pdf_bytes: bytes,
    *,
    media_dir: Path,
    ocr: bool = False,
    ocr_min_chars: int = 50,
) -> str:
    """
    Extract text per page; optionally OCR sparse pages with pytesseract when installed.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i in range(len(doc)):
        page = doc.load_page(i)
        text = page.get_text("text") or ""
        if ocr and len(text.strip()) < ocr_min_chars:
            try:
                import pytesseract
                from PIL import Image

                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img) or text
            except Exception:
                pass
        heading = f"## Page {i + 1}\n\n"
        parts.append(heading + text.strip())

    doc.close()

    # Tables via pdfplumber (best-effort append)
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as plumber:
            for pi, page in enumerate(plumber.pages, start=1):
                tables = page.extract_tables() or []
                if not tables:
                    continue
                parts.append(f"\n### Tables (pdfplumber) page {pi}\n")
                for ti, table in enumerate(tables, start=1):
                    if not table:
                        continue
                    parts.append(_table_to_gfm(table))
    except Exception:
        pass

    return "\n\n".join(p for p in parts if p.strip())


def _table_to_gfm(rows: list[list[str | None]]) -> str:
    clean: list[list[str]] = []
    for row in rows:
        clean.append([(c or "").replace("|", "\\|").replace("\n", " ") for c in row])
    if not clean:
        return ""
    width = max(len(r) for r in clean)
    norm = [r + [""] * (width - len(r)) for r in clean]
    header = norm[0]
    sep = ["---"] * width
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in norm[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"
