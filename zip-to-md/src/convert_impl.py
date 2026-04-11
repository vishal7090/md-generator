from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from io import StringIO
from pathlib import Path

from src.options import ConvertOptions

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"})
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


def _tool_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_repo_root(options: ConvertOptions) -> Path:
    env = (options.repo_root or os.environ.get("MD_GENERATOR_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    return _tool_root().parent


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


def _safe_extract_path(files_root: Path, member_name: str) -> Path | None:
    rel = member_name.replace("\\", "/").strip("/")
    if not rel or rel.endswith("/"):
        return None
    if rel.startswith("/") or ".." in Path(rel).parts:
        return None
    dest = (files_root / rel).resolve()
    try:
        dest.relative_to(files_root.resolve())
    except ValueError:
        return None
    return dest


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


def _run_tool(
    cwd: Path,
    argv: list[str],
    *,
    verbose: bool,
) -> tuple[int, str, str]:
    if verbose:
        print(f"[zip-to-md] run: cwd={cwd} {' '.join(argv)}", file=sys.stderr, flush=True)
    p = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out, (p.stderr or "")


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


def _convert_pdf_subprocess(
    abs_pdf: Path,
    repo: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    tool = repo / "pdf-to-md"
    conv = tool / "converter.py"
    if not conv.is_file():
        return "Content could not be parsed (pdf-to-md not found).\n"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        argv = [
            sys.executable,
            str(conv),
            str(abs_pdf),
            str(tmp),
            "--artifact-layout",
        ]
        if options.pdf_ocr:
            argv.append("--ocr")
        code, _, _ = _run_tool(tool, argv, verbose=options.verbose)
        if code != 0:
            return f"Content could not be parsed (pdf-to-md exit {code}).\n"
        body, _ = _merge_artifact_images(doc_md, tmp, final_images, prefix=member_slug)
        return body + "\n" if body else "(empty PDF conversion)\n"


def _convert_docx_subprocess(
    abs_docx: Path,
    repo: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    tool = repo / "word-to-md"
    conv = tool / "converter.py"
    if not conv.is_file():
        return "Content could not be parsed (word-to-md not found).\n"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out_md = tmp / "body.md"
        img_dir = tmp / "images"
        argv = [sys.executable, str(conv), str(abs_docx), str(out_md), "--images-dir", str(img_dir)]
        code, _, _ = _run_tool(tool, argv, verbose=options.verbose)
        if code != 0:
            return f"Content could not be parsed (word-to-md exit {code}).\n"
        if not out_md.is_file():
            return "Content could not be parsed (no output from word-to-md).\n"
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


def _convert_pptx_subprocess(
    abs_pptx: Path,
    repo: Path,
    final_images: Path,
    doc_md: Path,
    member_slug: str,
    options: ConvertOptions,
) -> str:
    tool = repo / "ppt-to-md"
    conv = tool / "converter.py"
    if not conv.is_file():
        return "Content could not be parsed (ppt-to-md not found).\n"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        argv = [
            sys.executable,
            str(conv),
            str(abs_pptx),
            str(tmp),
            "--artifact-layout",
            "--no-extract-embedded-deep",
        ]
        code, _, _ = _run_tool(tool, argv, verbose=options.verbose)
        if code != 0:
            return f"Content could not be parsed (ppt-to-md exit {code}).\n"
        body, _ = _merge_artifact_images(doc_md, tmp, final_images, prefix=member_slug)
        return body + "\n" if body else "(empty PPTX conversion)\n"


def _convert_xlsx_subprocess(
    abs_x: Path,
    repo: Path,
    options: ConvertOptions,
) -> str:
    tool = repo / "xlsx-to-md"
    conv = tool / "converter.py"
    if not conv.is_file():
        return "Content could not be parsed (xlsx-to-md not found).\n"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        argv = [sys.executable, str(conv), "-i", str(abs_x), "-o", str(tmp)]
        code, _, _ = _run_tool(tool, argv, verbose=options.verbose)
        if code != 0:
            return f"Content could not be parsed (xlsx-to-md exit {code}).\n"
        stem_md = tmp / f"{abs_x.stem}.md"
        if stem_md.is_file():
            return stem_md.read_text(encoding="utf-8", errors="replace") + "\n"
        mds = sorted(tmp.glob("*.md"))
        mds = [m for m in mds if m.name.lower() != "conversion_log.md"]
        if not mds:
            return "(no markdown from xlsx-to-md)\n"
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
    files_root: Path,
    images_dir: Path,
    doc_md: Path,
    repo: Path,
    options: ConvertOptions,
) -> str:
    suf = abs_path.suffix.lower()
    member_slug = _slug_for_member(rel_posix)

    if suf in IMAGE_SUFFIXES:
        return _handle_image(abs_path.read_bytes(), rel_posix, images_dir, doc_md, options)

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
        return _convert_pdf_subprocess(abs_path.resolve(), repo, images_dir, doc_md, member_slug, options)

    if options.enable_office and suf == ".docx":
        return _convert_docx_subprocess(abs_path.resolve(), repo, images_dir, doc_md, member_slug, options)

    if options.enable_office and suf == ".pptx":
        return _convert_pptx_subprocess(abs_path.resolve(), repo, images_dir, doc_md, member_slug, options)

    if options.enable_office and suf in (".xlsx", ".xlsm"):
        return _convert_xlsx_subprocess(abs_path.resolve(), repo, options)

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
    repo = _resolve_repo_root(options)

    index_paths: list[str] = []
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
            rel = dest.relative_to(files_root).as_posix()
            index_paths.append(rel)

    index_paths = sorted(set(index_paths))

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
            block = _handle_file_content(rel, abs_path, files_root, images_dir, doc_md, repo, options)
            lines.append(block)
            if not block.endswith("\n"):
                lines.append("\n")
        except Exception as e:
            lines.append(f"*Content could not be parsed: {e}*\n\n")

    doc_md.write_text("".join(lines), encoding="utf-8")
