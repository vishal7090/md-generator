"""PyMuPDF + pdfplumber adapter (refresh from pdf-to-md upstream when available)."""

from src.vendor_pdf_md.convert import pdf_to_markdown

__all__ = ["pdf_to_markdown"]
