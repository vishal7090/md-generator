"""Thin Mammoth → markdownify adapter (refresh from word-to-md upstream when available)."""

from md_generator.ppt.vendor_word_md.convert import docx_to_markdown_bundle

__all__ = ["docx_to_markdown_bundle"]
