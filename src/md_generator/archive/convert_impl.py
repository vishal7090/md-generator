from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from io import StringIO
from pathlib import Path

from md_generator.archive.options import DEFAULT_IMAGE_TO_MD_ENGINES, ConvertOptions

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"})
# Subset supported by sibling image-to-md (see image-to-md/src/io_util.py).
IMAGE_TO_MD_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"})
JUNK_NAMES = frozenset({".ds_store", "thumbs.db"})

_CODE_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cs": "csharp",
    ".sql": "sql",
    ".sh": "bash",
    ".ps1": "powershell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".m": "matlab",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".vue": "vue",
}


def _should_skip_zip_member(name: str) -> bool:
    n = name.replace("\\", "/").strip("/")
    if not n or n.endswith("/"):
        return False
    parts = n.split("/")
    if "__MACOSX" in parts:
        return True
    for p in parts:
        if p.upper() == ".DS_STORE" or p.lower() in JUNK_NAMES:
            return True
    return False


def _safe_member_path(extract_root: Path, member_name: str, jail_root: Path) -> Path | None:
    """Resolve member path under extract_root; must stay under jail_root (zip-slip safe)."""
    rel = member_name.replace("\\", "/").strip("/")
    if not rel or rel.endswith("/"):
        return None
    if rel.startswith("/") or ".." in Path(rel).parts:
        return None
    dest = (extract_root / rel).resolve()
    try:
        dest.relative_to(jail_root.resolve())
    except ValueError:
        return None
    return dest


def _safe_extract_path(files_root: Path, member_name: str) -> Path | None:
    return _safe_member_path(files_root, member_name, files_root)


def _nested_zip_depth(zip_path: Path, files_root: Path) -> int:
    """How many *_unzipped/ segments appear in the path (nesting level of prior expansions)."""
    try:
        rel = zip_path.resolve().relative_to(files_root.resolve())
    except ValueError:
        return 999
    return sum(1 for part in rel.parts if part.endswith("_unzipped"))


def _allocate_unzip_dir(zip_path: Path) -> Path:
    parent = zip_path.parent
    stem = zip_path.stem
    base = parent / f"{stem}_unzipped"
    if not base.exists():
        return base
    if base.is_dir():
        n = 2
        while n <= 10_000:
            cand = parent / f"{stem}_unzipped_{n}"
            if not cand.exists():
                return cand
            n += 1
    tag = hashlib.sha256(str(zip_path.resolve()).encode()).hexdigest()[:10]
    return parent / f"{stem}_unzipped_{tag}"


def _extract_zip_members_to_dir(
    archive: Path,
    extract_root: Path,
    jail_root: Path,
    *,
    verbose: bool,
) -> bool:
    """Extract all members of archive under extract_root (paths confined to jail_root). Returns False on failure."""
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            for name in zf.namelist():
                norm = name.replace("\\", "/")
                if _should_skip_zip_member(norm):
                    continue
                dest = _safe_member_path(extract_root, norm, jail_root)
                if dest is None:
                    if verbose:
                        print(f"[zip-to-md] skip unsafe path in {archive.name}: {norm!r}", file=sys.stderr, flush=True)
                    continue
                if norm.endswith("/"):
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    except (zipfile.BadZipFile, OSError) as e:
        if verbose:
            print(f"[zip-to-md] bad zip {archive}: {e}", file=sys.stderr, flush=True)
        return False
    return True


def _expand_nested_zips(files_root: Path, options: ConvertOptions) -> None:
    if not options.expand_nested_zips:
        return
    jail = files_root.resolve()
    max_depth = options.max_nested_zip_depth
    processed: set[str] = set()

    while True:
        wave: list[Path] = []
        for zip_path in sorted(files_root.rglob("*.zip")):
            if not zip_path.is_file():
                continue
            key = str(zip_path.resolve())
            if key in processed:
                continue
            if not zipfile.is_zipfile(zip_path):
                processed.add(key)
                continue
            depth = _nested_zip_depth(zip_path, files_root)
            if depth >= max_depth:
                processed.add(key)
                if options.verbose:
                    print(
                        f"[zip-to-md] skip nested zip (max depth {max_depth}): {zip_path.relative_to(files_root)}",
                        file=sys.stderr,
                        flush=True,
                    )
                continue
            wave.append(zip_path)

        if not wave:
            break

        for zip_path in wave:
            key = str(zip_path.resolve())
            processed.add(key)
            dest_dir = _allocate_unzip_dir(zip_path)
            if options.verbose:
                print(
                    f"[zip-to-md] expand {zip_path.relative_to(files_root)} -> {dest_dir.relative_to(files_root)}/",
                    file=sys.stderr,
                    flush=True,
                )
            ok = _extract_zip_members_to_dir(zip_path, dest_dir, jail, verbose=options.verbose)
            if not ok and dest_dir.exists() and not any(dest_dir.iterdir()):
                try:
                    dest_dir.rmdir()
                except OSError:
                    pass


def _all_file_paths_under(files_root: Path) -> list[str]:
    paths: list[str] = []
    for p in sorted(files_root.rglob("*")):
        if p.is_file():
            paths.append(p.relative_to(files_root).as_posix())
    return paths


def _csv_to_gfm(data: bytes, encoding: str = "utf-8") -> str:
    text = data.decode(encoding, errors="replace")
    f = StringIO(text)
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        f.seek(0)
        reader = csv.reader(f, dialect)
        rows = list(reader)
    except Exception:
        f.seek(0)
        rows = list(csv.reader(f))
    if not rows:
        return "(empty CSV)\n"
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    header = norm[0]
    sep = ["---"] * width
    lines = [
        "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in norm[1:]:
        lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in row) + " |")
    return "\n".join(lines) + "\n"


def _slug_for_member(rel_posix: str) -> str:
    h = hashlib.sha256(rel_posix.encode("utf-8")).hexdigest()[:10]
    base = re.sub(r"[^\w.\-]+", "_", rel_posix.replace("/", "__"))[:60].strip("_") or "file"
    return f"{base}_{h}"


def _rewrite_md_image_paths(
    md: str,
    old_to_new: dict[str, str],
) -> str:
    pairs = sorted(old_to_new.items(), key=lambda kv: len(kv[0]), reverse=True)

    def repl(m: re.Match[str]) -> str:
        alt, path = m.group(1), m.group(2).strip()
        path_clean = path.split("?", 1)[0].strip().lstrip("./")
        path_norm = path_clean.replace("\\", "/")
        for old, new in pairs:
            o = old.lstrip("./").replace("\\", "/")
            if path_norm == o or path_norm.endswith("/" + o):
                return f"![{alt}]({new})"
        return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md)


def _merge_artifact_images(
    doc_md: Path,
    artifact_dir: Path,
    final_images_dir: Path,
    *,
    prefix: str,
) -> tuple[str, dict[str, str]]:
    inner_md = artifact_dir / "document.md"
    if not inner_md.is_file():
        return "", {}
    body = inner_md.read_text(encoding="utf-8", errors="replace")
    inner_img = artifact_dir / "assets" / "images"
    old_to_new: dict[str, str] = {}
    if inner_img.is_dir():
        for p in sorted(inner_img.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(inner_img).as_posix()
            tag = hashlib.sha256(rel.encode()).hexdigest()[:8]
            new_name = f"{prefix}_{tag}_{Path(rel).name}"
            dest = final_images_dir / new_name
            if dest.exists():
                dest = final_images_dir / f"{prefix}_{tag}_{Path(rel).stem}_x{hashlib.sha256(rel.encode()).hexdigest()[:4]}{Path(rel).suffix}"
            shutil.copy2(p, dest)
            old = f"assets/images/{rel}"
            new = dest.relative_to(doc_md.parent.resolve()).as_posix()
            old_to_new[old] = new
            old_to_new[rel] = new
            old_to_new[Path(rel).name] = new
    body = _rewrite_md_image_paths(body, old_to_new)
    for sub in ("charts", "tables", "media", "other"):
        src_sub = artifact_dir / "assets" / sub
        if src_sub.is_dir():
            dst_sub = final_images_dir.parent / sub
            dst_sub.mkdir(parents=True, exist_ok=True)
            for p in src_sub.rglob("*"):
                if p.is_file():
                    rel_p = p.relative_to(src_sub).as_posix()
                    tag = hashlib.sha256(rel_p.encode()).hexdigest()[:8]
                    dest = dst_sub / f"{prefix}_{tag}_{p.name}"
                    if dest.exists():
                        dest = dst_sub / f"{prefix}_{tag}_{p.stem}_x{hashlib.sha256(rel_p.encode()).hexdigest()[:4]}{p.suffix}"
                    shutil.copy2(p, dest)
    return body, old_to_new


def _missing_dep_message(feature: str, extra: str) -> str:
    return f"Content could not be parsed ({feature} unavailable: install mdengine[{extra}]).\n"


def _convert_pdf_office(
    abs_pdf: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    import tempfile

    try:
        from md_generator.pdf.pdf_extract import ConvertOptions as PdfOpts, convert_pdf
        from md_generator.pdf.utils import resolve_output
    except ImportError:
        return _missing_dep_message("PDF conversion", "pdf")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        resolved = resolve_output(tmp, artifact_layout=True, images_dir=None)
        opts = PdfOpts(
            use_ocr=bool(options.pdf_ocr),
            ocr_min_chars=40,
            verbose=options.verbose,
        )
        try:
            convert_pdf(abs_pdf.resolve(), resolved, opts)
        except Exception as e:
            return f"Content could not be parsed (pdf conversion failed: {e}).\n"
        body, _ = _merge_artifact_images(doc_md, tmp, final_images, prefix=member_slug)
        return body + "\n" if body else "(empty PDF conversion)\n"


def _convert_docx_office(
    abs_docx: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    import tempfile

    try:
        from md_generator.word.converter import convert_docx_to_markdown
    except ImportError:
        return _missing_dep_message("DOCX conversion", "word")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out_md = tmp / "body.md"
        img_dir = tmp / "images"
        try:
            convert_docx_to_markdown(abs_docx.resolve(), out_md, images_dir=img_dir, verbose=options.verbose)
        except Exception as e:
            return f"Content could not be parsed (docx conversion failed: {e}).\n"
        if not out_md.is_file():
            return "Content could not be parsed (no output from word conversion).\n"
        body = out_md.read_text(encoding="utf-8", errors="replace")
        old_to_new: dict[str, str] = {}
        if img_dir.is_dir():
            for p in sorted(img_dir.iterdir()):
                if not p.is_file():
                    continue
                dest = final_images / f"{member_slug}_{p.name}"
                if dest.exists():
                    dest = final_images / f"{member_slug}_{p.stem}_{hashlib.sha256(p.name.encode()).hexdigest()[:6]}{p.suffix}"
                shutil.copy2(p, dest)
                old_rel = f"images/{p.name}"
                new_rel = dest.relative_to(doc_md.parent.resolve()).as_posix()
                old_to_new[old_rel] = new_rel
                old_to_new[p.name] = new_rel
        body = _rewrite_md_image_paths(body, old_to_new)
        return body + "\n"


def _convert_pptx_office(
    abs_pptx: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    import tempfile

    try:
        from md_generator.ppt.convert_impl import convert_pptx
        from md_generator.ppt.options import ConvertOptions as PptOpts
    except ImportError:
        return _missing_dep_message("PPTX conversion", "ppt")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        opts = PptOpts(artifact_layout=True, extract_embedded_deep=False, verbose=options.verbose)
        try:
            convert_pptx(abs_pptx.resolve(), tmp, opts)
        except Exception as e:
            return f"Content could not be parsed (pptx conversion failed: {e}).\n"
        body, _ = _merge_artifact_images(doc_md, tmp, final_images, prefix=member_slug)
        return body + "\n" if body else "(empty PPTX conversion)\n"


def _convert_xlsx_office(abs_x: Path, _options: ConvertOptions) -> str:
    import tempfile

    try:
        from md_generator.xlsx.convert_config import ConvertConfig
        from md_generator.xlsx.converter_core import convert_excel_to_markdown
    except ImportError:
        return _missing_dep_message("Excel conversion", "xlsx")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            convert_excel_to_markdown(abs_x.resolve(), tmp, config=ConvertConfig())
        except Exception as e:
            return f"Content could not be parsed (xlsx conversion failed: {e}).\n"
        stem_md = tmp / f"{abs_x.stem}.md"
        if stem_md.is_file():
            return stem_md.read_text(encoding="utf-8", errors="replace") + "\n"
        mds = sorted(tmp.glob("*.md"))
        mds = [m for m in mds if m.name.lower() != "conversion_log.md"]
        if not mds:
            return "(no markdown from xlsx conversion)\n"
        return mds[0].read_text(encoding="utf-8", errors="replace") + "\n"


def _image_ocr_note(path: Path, options: ConvertOptions) -> str:
    if not options.image_ocr:
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "\n\n*(Image OCR unavailable: install pytesseract and Pillow.)*\n"
    try:
        with Image.open(path) as im:
            text = pytesseract.image_to_string(im).strip()
        if text:
            return f"\n\n**OCR text:**\n\n```\n{text[:8000]}\n```\n"
    except Exception as e:
        return f"\n\n*(OCR failed: {e})*\n"
    return ""


def _collect_unique_raster_paths(files_root: Path, images_dir: Path) -> list[Path]:
    """
    All supported raster files under extracted files and merged images.
    Dedupes by resolved path, then by file digest so the same pixel file (e.g. under
    assets/files and assets/images) is only OCR'd once — avoids PIL edge cases.
    """
    seen: set[str] = set()
    candidates: list[Path] = []
    for root in (files_root, images_dir):
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in IMAGE_TO_MD_EXTENSIONS:
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(p)

    by_digest: dict[str, Path] = {}
    for p in candidates:
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest not in by_digest:
            by_digest[digest] = p
    return sorted(by_digest.values(), key=lambda x: str(x).lower())


def _postpass_image_to_markdown(
    files_root: Path,
    images_dir: Path,
    options: ConvertOptions,
) -> str:
    """
    One image-to-md run on a flat temp copy of every raster under assets/files and assets/images
    (includes merged office/PDF images).
    """
    if not options.use_image_to_md:
        return ""

    paths = _collect_unique_raster_paths(files_root, images_dir)
    if not paths:
        return ""

    try:
        import os
        import tempfile
        import uuid

        from md_generator.image.convert_impl import ConvertOptions as ImgOpts, convert_image_paths
    except ImportError:
        return "\n\n*(Post-pass image-to-md skipped: install mdengine[image].)*\n"

    raw_engines = options.image_to_md_engines.strip() or DEFAULT_IMAGE_TO_MD_ENGINES
    engines = tuple(p.strip().lower() for p in raw_engines.split(",") if p.strip())
    strategy: str = options.image_to_md_strategy if options.image_to_md_strategy in ("best", "compare") else "best"
    title = (options.image_to_md_title or "OCR - raster images (extracted and merged)").strip()[:240]

    out_md = Path(tempfile.gettempdir()) / f"zip-to-md-ocr-{uuid.uuid4().hex}.md"
    out_md.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory() as td_root:
            flat = (Path(td_root) / "flat").resolve()
            flat.mkdir(parents=True, exist_ok=True)
            for i, src in enumerate(paths):
                suf = src.suffix.lower() or ".img"
                tag = hashlib.sha256(str(src.resolve()).encode()).hexdigest()[:12]
                name = f"{i:05d}_{tag}{suf}"
                shutil.copy2(src.resolve(), flat / name)
            ordered = sorted((p for p in flat.iterdir() if p.is_file()), key=lambda p: p.name.lower())
            if not ordered:
                return ""
            tess_cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
            opts = ImgOpts(
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
            try:
                convert_image_paths(ordered, out_md, opts)
            except ValueError as e:
                return f"\n\n*(Post-pass image-to-md: {e})*\n"
            except Exception as e:
                return f"\n\n*(Post-pass image-to-md failed: {e})*\n"
            if not out_md.is_file():
                return "\n\n*(Post-pass image-to-md produced no output file.)*\n"
            body = out_md.read_text(encoding="utf-8", errors="replace").strip()
            if not body:
                return "\n\n*(Post-pass image-to-md returned empty document.)*\n"
            block = _trim_text(body + "\n", options.max_bytes + 500_000)
            return f"\n\n## Post-pass: image-to-md (all rasters)\n\n{block}"
    finally:
        out_md.unlink(missing_ok=True)


def _handle_image(
    data: bytes,
    rel_posix: str,
    images_dir: Path,
    doc_md: Path,
    options: ConvertOptions,
) -> str:
    slug = _slug_for_member(rel_posix)
    ext = Path(rel_posix).suffix.lower() or ".bin"
    dest = images_dir / f"{slug}{ext}"
    dest.write_bytes(data)
    rel_link = dest.relative_to(doc_md.parent.resolve()).as_posix()
    line = f"![{Path(rel_posix).name}]({rel_link})\n"
    if options.image_ocr:
        line += _image_ocr_note(dest, options)
    return line


def _trim_text(s: str, max_bytes: int) -> str:
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return s
    cut = s.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    return cut + "\n\n*(Truncated: content exceeded max-bytes limit.)*\n"


def _handle_file_content(
    rel_posix: str,
    abs_path: Path,
    images_dir: Path,
    doc_md: Path,
    options: ConvertOptions,
) -> str:
    suf = abs_path.suffix.lower()
    member_slug = _slug_for_member(rel_posix)

    if suf in IMAGE_SUFFIXES:
        return _handle_image(abs_path.read_bytes(), rel_posix, images_dir, doc_md, options)

    if suf == ".zip":
        parent = str(Path(rel_posix).parent.as_posix())
        stem = abs_path.stem
        if parent in (".", ""):
            hint = f"`{stem}_unzipped/` (under `assets/files/`)"
        else:
            hint = f"`{parent}/{stem}_unzipped/` (or `..._unzipped_N/` if that name was taken)"
        if options.expand_nested_zips:
            return (
                f"*Nested ZIP archive. With recursive expansion enabled, members are extracted next to "
                f"this file, typically under {hint}.*\n"
            )
        return f"*Nested ZIP (`{rel_posix}`); recursive expansion is disabled (`--no-expand-nested-zips`).*\n"

    if suf == ".txt":
        t = abs_path.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"
        return _trim_text(t, options.max_bytes)

    if suf == ".md":
        t = abs_path.read_text(encoding="utf-8", errors="replace")
        return _trim_text(t, options.max_bytes)

    if suf == ".csv":
        return _trim_text(_csv_to_gfm(abs_path.read_bytes()), options.max_bytes)

    if suf == ".json":
        try:
            obj = json.loads(abs_path.read_text(encoding="utf-8"))
            pretty = json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception:
            pretty = abs_path.read_text(encoding="utf-8", errors="replace")
        block = f"```json\n{pretty}\n```\n"
        return _trim_text(block, options.max_bytes + 100)

    if suf == ".xml":
        raw = abs_path.read_text(encoding="utf-8", errors="replace")
        block = f"```xml\n{raw}\n```\n"
        return _trim_text(block, options.max_bytes + 100)

    if options.enable_office and suf == ".pdf":
        return _convert_pdf_office(abs_path.resolve(), images_dir, doc_md, member_slug, options)

    if options.enable_office and suf == ".docx":
        return _convert_docx_office(abs_path.resolve(), images_dir, doc_md, member_slug, options)

    if options.enable_office and suf == ".pptx":
        return _convert_pptx_office(abs_path.resolve(), images_dir, doc_md, member_slug, options)

    if options.enable_office and suf in (".xlsx", ".xlsm"):
        return _convert_xlsx_office(abs_path.resolve(), options)

    lang = _CODE_LANG.get(suf)
    if lang:
        raw = abs_path.read_text(encoding="utf-8", errors="replace")
        block = f"```{lang}\n{raw.rstrip()}\n```\n"
        return _trim_text(block, options.max_bytes + 100)

    try:
        raw = abs_path.read_bytes()
        raw.decode("utf-8")
        text = raw.decode("utf-8", errors="replace")
        if sum(1 for c in text if c.isprintable() or c in "\n\r\t") / max(len(text), 1) > 0.92:
            block = f"```\n{text.rstrip()}\n```\n"
            return _trim_text(block, options.max_bytes + 100)
    except Exception:
        pass

    return f"*Unsupported file type or binary content: `{rel_posix}`*\n"


def convert_zip(
    input_path: Path,
    output_path: Path,
    options: ConvertOptions,
) -> None:
    input_path = input_path.resolve()
    if input_path.suffix.lower() != ".zip":
        raise ValueError("Input must be a .zip file")

    if not options.artifact_layout:
        raise ValueError("Only artifact layout is supported (output must be a directory)")

    out_dir = output_path.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    files_root = out_dir / "assets" / "files"
    images_dir = out_dir / "assets" / "images"
    files_root.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    doc_md = out_dir / "document.md"

    with zipfile.ZipFile(input_path, "r") as zf:
        for name in zf.namelist():
            norm = name.replace("\\", "/")
            if _should_skip_zip_member(norm):
                continue
            dest = _safe_extract_path(files_root, norm)
            if dest is None:
                continue
            if norm.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

    _expand_nested_zips(files_root, options)
    index_paths = _all_file_paths_under(files_root)

    lines: list[str] = [
        "# ZIP Content Documentation\n",
        "## File Index\n",
    ]
    for p in index_paths:
        lines.append(f"- `{p}`\n")
    lines.append("\n## Extracted Content\n\n")

    for rel in index_paths:
        abs_path = files_root / rel
        if not abs_path.is_file():
            continue
        lines.append(f"### /{rel}\n\n")
        try:
            block = _handle_file_content(rel, abs_path, images_dir, doc_md, options)
            lines.append(block)
            if not block.endswith("\n"):
                lines.append("\n")
        except Exception as e:
            lines.append(f"*Content could not be parsed: {e}*\n\n")

    appendix = _postpass_image_to_markdown(files_root, images_dir, options)
    if appendix:
        lines.append(appendix)
        if not appendix.endswith("\n"):
            lines.append("\n")

    doc_md.write_text("".join(lines), encoding="utf-8")
