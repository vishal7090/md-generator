"""Orchestrate image discovery, OCR backends, and Markdown emission."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from src.backends.base import OcrBackend
from src.backends.easy import EasyOcrBackend
from src.backends.paddle import PaddleBackend
from src.backends.tesseract import TesseractBackend
from src.emit import markdown_best, markdown_compare, pick_best_text
from src.io_util import iter_image_paths, iter_image_paths_recursive, load_pil_rgb


@dataclass(frozen=True)
class ConvertOptions:
    engines: tuple[str, ...]
    strategy: Literal["compare", "best"]
    title: str
    tess_lang: str
    tesseract_cmd: str | None
    paddle_lang: str
    paddle_use_angle_cls: bool
    easy_langs: tuple[str, ...]
    verbose: bool


def _parse_engine_ids(parts: tuple[str, ...]) -> tuple[str, ...]:
    allowed = {"tess", "paddle", "easy"}
    out: list[str] = []
    for p in parts:
        q = str(p).strip().lower()
        if not q:
            continue
        if q not in allowed:
            raise ValueError(f"Invalid engine {q!r}; allowed: tess, paddle, easy")
        out.append(q)
    if not out:
        raise ValueError("At least one engine is required.")
    return tuple(out)


def build_backends(opts: ConvertOptions) -> list[OcrBackend]:
    backends = []
    for eid in opts.engines:
        if eid == "tess":
            backends.append(
                TesseractBackend(
                    lang=opts.tess_lang,
                    tesseract_cmd=opts.tesseract_cmd,
                    verbose=opts.verbose,
                )
            )
        elif eid == "paddle":
            backends.append(
                PaddleBackend(
                    lang=opts.paddle_lang,
                    use_angle_cls=opts.paddle_use_angle_cls,
                    verbose=opts.verbose,
                )
            )
        elif eid == "easy":
            backends.append(EasyOcrBackend(langs=opts.easy_langs, verbose=opts.verbose))
    return backends


def convert_image_paths(paths: list[Path], output_md: Path, options: ConvertOptions) -> None:
    """Run OCR on an explicit ordered list of image paths; write one Markdown file."""
    if not paths:
        raise ValueError("No image paths to convert")

    engines = _parse_engine_ids(options.engines)
    opts = replace(options, engines=engines)
    backends = build_backends(opts)
    priority_names = [b.name for b in backends]

    if opts.strategy == "compare":
        sections: list[tuple[str, dict[str, str]]] = []
        for p in paths:
            image = load_pil_rgb(p)
            by_name: dict[str, str] = {b.name: b.extract(image) for b in backends}
            sections.append((p.name, by_name))
        md = markdown_compare(opts.title, sections)
    else:
        best_sections: list[tuple[str, str]] = []
        for p in paths:
            image = load_pil_rgb(p)
            by_name: dict[str, str] = {b.name: b.extract(image) for b in backends}
            best_sections.append((p.name, pick_best_text(by_name, priority_names)))
        md = markdown_best(opts.title, best_sections)

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(md, encoding="utf-8")


def convert_images(input_path: Path, output_md: Path, options: ConvertOptions) -> None:
    """Read images from file or directory (non-recursive), run OCR, write one Markdown file."""
    paths = iter_image_paths(Path(input_path))
    if not paths:
        raise ValueError(f"No supported images found under: {input_path}")
    convert_image_paths(paths, output_md, options)


def convert_images_recursive(input_path: Path, output_md: Path, options: ConvertOptions) -> None:
    """Like convert_images, but if input is a directory, collect images recursively (e.g. after ZIP extract)."""
    root = Path(input_path).resolve()
    if root.is_file():
        paths = iter_image_paths(root)
    elif root.is_dir():
        paths = iter_image_paths_recursive(root)
    else:
        raise FileNotFoundError(f"image-to-md: input not found: {input_path}")
    if not paths:
        raise ValueError(f"No supported images found under: {input_path}")
    convert_image_paths(paths, output_md, options)
