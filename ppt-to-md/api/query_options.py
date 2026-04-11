from __future__ import annotations

from src.options import ConvertOptions


def convert_options_from_query(
    *,
    extract_embedded_deep: bool = True,
    max_unpack_depth: int = 2,
    emit_extracted_txt_md: bool = True,
    extracted_pdf_ocr: bool = True,
    extracted_pdf_ocr_min_chars: int = 50,
    chart_data: bool = True,
    chart_image: bool = True,
    table_csv: bool = True,
    extracted_docx_md: bool = True,
    extracted_pdf_md: bool = True,
    extracted_xlsx_md: bool = True,
) -> ConvertOptions:
    """Map API query parameters to ConvertOptions (artifact layout forced at call site)."""
    return ConvertOptions(
        artifact_layout=True,
        chart_data=chart_data,
        chart_image=chart_image,
        table_csv=table_csv,
        extract_embedded_deep=extract_embedded_deep,
        max_unpack_depth=max_unpack_depth,
        emit_extracted_txt_md=emit_extracted_txt_md,
        extracted_docx_md=extracted_docx_md,
        extracted_pdf_md=extracted_pdf_md,
        extracted_xlsx_md=extracted_xlsx_md,
        extracted_pdf_ocr=extracted_pdf_ocr,
        extracted_pdf_ocr_min_chars=extracted_pdf_ocr_min_chars,
        verbose=False,
    )
