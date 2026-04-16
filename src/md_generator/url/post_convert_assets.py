from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from md_generator.url.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions

INLINE_CAP = 48_000

_RASTER_IMAGE_EXT = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"})


def _slug(stem: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE).strip("_")
    return s[:72] or "file"


def _idx_slug(path: Path, idx: int) -> str:
    import hashlib

    h = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:8]
    return f"{idx:04d}_{_slug(path.stem)}_{h}"


def _rel_from_root(target: Path, page_root: Path) -> str:
    return target.resolve().relative_to(page_root.resolve()).as_posix()


def _log_append(entries: list[dict], path: str, status: str, detail: str = "") -> None:
    entries.append({"path": path, "status": status, "detail": detail})


def _files_and_assets_parent(page_root: Path, options: ConvertOptions) -> tuple[Path | None, Path]:
    if options.artifact_layout:
        files_dir = page_root / "assets" / "files"
        assets_parent = page_root / "assets"
    else:
        files_dir = page_root / "files"
        assets_parent = page_root
    if not files_dir.is_dir():
        return None, assets_parent
    return files_dir, assets_parent


def _images_dir(page_root: Path, options: ConvertOptions) -> Path | None:
    if options.artifact_layout:
        d = page_root / "assets" / "images"
    else:
        d = page_root / "images"
    return d if d.is_dir() else None


def process_downloaded_files(page_root: Path, options: ConvertOptions) -> str:
    """
    Convert files under assets/files (or files/ in classic mode) using internal md_generator
    converters. Returns Markdown appendix for document.md (may be empty).
    """
    if not options.convert_downloaded_assets and not options.convert_downloaded_images:
        return ""

    files_dir, assets_parent = _files_and_assets_parent(page_root, options)
    log_entries: list[dict] = []
    blocks: list[str] = []

    extracted_md = assets_parent / "extracted_md"
    extracted_md.mkdir(parents=True, exist_ok=True)

    if options.convert_downloaded_assets and files_dir is not None:
        file_paths = sorted(p for p in files_dir.iterdir() if p.is_file())
    else:
        file_paths = []

    for idx, src in enumerate(file_paths, start=1):
        slug = _idx_slug(src, idx)
        suf = src.suffix.lower()

        if suf in (".doc", ".ppt"):
            _log_append(log_entries, src.name, "skip", "legacy .doc/.ppt not supported")
            continue

        if suf == ".pdf":
            _try_pdf(src, slug, extracted_md, page_root, options, log_entries, blocks)
        elif suf == ".docx":
            _try_docx(src, slug, extracted_md, assets_parent, page_root, options, log_entries, blocks)
        elif suf == ".pptx":
            _try_pptx(src, slug, extracted_md, page_root, options, log_entries, blocks)
        elif suf in (".xlsx", ".xlsm", ".csv"):
            _try_xlsx(src, slug, extracted_md, page_root, options, log_entries, blocks)
        elif suf == ".zip":
            _try_zip(src, slug, extracted_md, page_root, options, log_entries, blocks)
        elif suf in (".txt", ".json", ".xml"):
            _try_text(src, slug, extracted_md, page_root, options, log_entries, blocks)
        else:
            _log_append(log_entries, src.name, "skip", f"no converter for {suf!r}")

    if options.convert_downloaded_images:
        _try_images_ocr(page_root, extracted_md, options, log_entries, blocks)

    log_path = assets_parent / "asset_convert_log.json"
    log_path.write_text(json.dumps({"entries": log_entries}, indent=2), encoding="utf-8")

    if not blocks:
        return ""

    return "\n## Downloaded files converted to Markdown\n\n" + "\n".join(blocks) + "\n"


def _try_pdf(
    src: Path,
    slug: str,
    extracted_md: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.pdf.pdf_extract import ConvertOptions as PdfConvertOptions
        from md_generator.pdf.pdf_extract import convert_pdf_to_artifact_dir
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing pdf extra: {e}")
        return
    out_sub = extracted_md / f"{slug}_pdf"
    try:
        out_sub.mkdir(parents=True, exist_ok=True)
        convert_pdf_to_artifact_dir(
            src,
            out_sub,
            PdfConvertOptions(
                use_ocr=options.post_convert_pdf_ocr,
                ocr_min_chars=options.post_convert_pdf_ocr_min_chars,
                verbose=options.verbose,
            ),
        )
        doc = out_sub / "document.md"
        if doc.is_file():
            rel = _rel_from_root(doc, page_root)
            body = doc.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View extracted PDF]({rel})"
            blocks.append(f"### `{src.name}` (PDF)\n\n{snippet}\n")
            _log_append(log_entries, src.name, "ok", "pdf")
        else:
            _log_append(log_entries, src.name, "error", "no document.md after pdf convert")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert pdf {src}: {e}", file=sys.stderr)


def _try_docx(
    src: Path,
    slug: str,
    extracted_md: Path,
    assets_parent: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.word.converter import convert_docx_to_markdown
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing word extra: {e}")
        return
    media = assets_parent / "extracted_md_media" / slug
    md_out = extracted_md / f"{slug}.md"
    try:
        media.mkdir(parents=True, exist_ok=True)
        convert_docx_to_markdown(src, md_out, images_dir=media, verbose=options.verbose)
        if md_out.is_file():
            rel = _rel_from_root(md_out, page_root)
            body = md_out.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View extracted Word]({rel})"
            blocks.append(f"### `{src.name}` (DOCX)\n\n{snippet}\n")
            _log_append(log_entries, src.name, "ok", "docx")
        else:
            _log_append(log_entries, src.name, "error", "no output md")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert docx {src}: {e}", file=sys.stderr)


def _try_pptx(
    src: Path,
    slug: str,
    extracted_md: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.ppt.convert_impl import convert_pptx
        from md_generator.ppt.options import ConvertOptions as PptConvertOptions
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing ppt extra: {e}")
        return
    out_sub = extracted_md / f"{slug}_ppt"
    try:
        ppt_opts = PptConvertOptions(
            artifact_layout=True,
            extract_embedded_deep=options.post_convert_ppt_embedded_deep,
            verbose=options.verbose,
        )
        convert_pptx(src, out_sub, ppt_opts)
        doc = out_sub / "document.md"
        if doc.is_file():
            rel = _rel_from_root(doc, page_root)
            body = doc.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View extracted PPTX]({rel})"
            blocks.append(f"### `{src.name}` (PPTX)\n\n{snippet}\n")
            _log_append(log_entries, src.name, "ok", "pptx")
        else:
            _log_append(log_entries, src.name, "error", "no document.md after pptx convert")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert pptx {src}: {e}", file=sys.stderr)


def _try_xlsx(
    src: Path,
    slug: str,
    extracted_md: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.xlsx.converter_core import convert_excel_to_markdown
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing xlsx extra: {e}")
        return
    out_sub = extracted_md / f"{slug}_xlsx"
    try:
        out_sub.mkdir(parents=True, exist_ok=True)
        convert_excel_to_markdown(src, out_sub, config=None)
        md_files = sorted(out_sub.glob("*.md"))
        if not md_files:
            _log_append(log_entries, src.name, "error", "no markdown from xlsx")
            return
        primary = md_files[0]
        rel = _rel_from_root(primary, page_root)
        body = primary.read_text(encoding="utf-8", errors="replace")
        snippet = body if len(body) <= INLINE_CAP else f"[View extracted spreadsheet]({rel})"
        blocks.append(f"### `{src.name}` (Excel/CSV)\n\n{snippet}\n")
        _log_append(log_entries, src.name, "ok", "xlsx")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert xlsx {src}: {e}", file=sys.stderr)


def _try_zip(
    src: Path,
    slug: str,
    extracted_md: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.archive.convert_impl import convert_zip
        from md_generator.archive.options import ConvertOptions as ArchiveConvertOptions
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing archive extra: {e}")
        return
    out_sub = extracted_md / f"{slug}_zip"
    try:
        convert_zip(
            src,
            out_sub,
            ArchiveConvertOptions(verbose=options.verbose, artifact_layout=True),
        )
        doc = out_sub / "document.md"
        if doc.is_file():
            rel = _rel_from_root(doc, page_root)
            body = doc.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View extracted ZIP]({rel})"
            blocks.append(f"### `{src.name}` (ZIP)\n\n{snippet}\n")
            _log_append(log_entries, src.name, "ok", "zip")
        else:
            _log_append(log_entries, src.name, "error", "no document.md after zip convert")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert zip {src}: {e}", file=sys.stderr)


def _try_text(
    src: Path,
    slug: str,
    extracted_md: Path,
    page_root: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.text.convert_impl import convert_text_file
        from md_generator.text.options import ConvertOptions as TextConvertOptions
    except ImportError as e:
        _log_append(log_entries, src.name, "error", f"missing text module: {e}")
        return
    out_sub = extracted_md / f"{slug}_text"
    try:
        topts = TextConvertOptions(artifact_layout=True, verbose=options.verbose)
        convert_text_file(src, out_sub, topts)
        doc = out_sub / "document.md"
        if doc.is_file():
            rel = _rel_from_root(doc, page_root)
            body = doc.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View extracted text]({rel})"
            blocks.append(f"### `{src.name}` (text/JSON/XML)\n\n{snippet}\n")
            _log_append(log_entries, src.name, "ok", "text")
        else:
            _log_append(log_entries, src.name, "error", "no document.md after text convert")
    except Exception as e:
        _log_append(log_entries, src.name, "error", str(e))
        if options.verbose:
            print(f"url post-convert text {src}: {e}", file=sys.stderr)


def _try_images_ocr(
    page_root: Path,
    extracted_md: Path,
    options: ConvertOptions,
    log_entries: list[dict],
    blocks: list[str],
) -> None:
    try:
        from md_generator.image.convert_impl import ConvertOptions as ImageConvertOptions
        from md_generator.image.convert_impl import convert_image_paths
    except ImportError as e:
        _log_append(log_entries, "(images)", "error", f"missing image extra: {e}")
        return

    img_root = _images_dir(page_root, options)
    if not img_root:
        return

    paths = sorted(
        p for p in img_root.iterdir() if p.is_file() and p.suffix.lower() in _RASTER_IMAGE_EXT
    )[:30]
    if not paths:
        return

    raw_engines = options.convert_downloaded_image_to_md_engines.strip() or DEFAULT_IMAGE_TO_MD_ENGINES
    engines = tuple(p.strip().lower() for p in raw_engines.split(",") if p.strip())
    strategy: str = (
        options.convert_downloaded_image_to_md_strategy
        if options.convert_downloaded_image_to_md_strategy in ("best", "compare")
        else "best"
    )
    title = (options.convert_downloaded_image_to_md_title or "Downloaded images (OCR)").strip()[:240]
    tess_cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")

    img_opts = ImageConvertOptions(
        engines=engines,
        strategy=strategy,  # type: ignore[arg-type]
        title=title,
        tess_lang="eng",
        tesseract_cmd=tess_cmd,
        paddle_lang="en",
        paddle_use_angle_cls=True,
        easy_langs=("en",),
        verbose=options.verbose,
    )
    out_md = extracted_md / "downloaded_images_ocr.md"
    try:
        convert_image_paths(paths, out_md, img_opts)
        if out_md.is_file():
            rel = _rel_from_root(out_md, page_root)
            body = out_md.read_text(encoding="utf-8", errors="replace")
            snippet = body if len(body) <= INLINE_CAP else f"[View OCR bundle]({rel})"
            blocks.append(f"### {title}\n\n{snippet}\n")
            _log_append(log_entries, "images_ocr", "ok", str(len(paths)))
    except Exception as e:
        _log_append(log_entries, "images_ocr", "error", str(e))
        if options.verbose:
            print(f"url post-convert images: {e}", file=sys.stderr)
