"""Discover image inputs and load PIL images."""

from __future__ import annotations

from pathlib import Path

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"})


def is_image_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def iter_image_paths(root: Path) -> list[Path]:
    """
    If root is a file, return [root] when it looks like an image.
    If root is a directory, return sorted image files (non-recursive).
    """
    root = Path(root).resolve()
    if root.is_file():
        if not is_image_path(root):
            raise ValueError(
                f"image-to-md: input file is not a supported image type: {root} "
                f"(expected extension in {sorted(IMAGE_EXTENSIONS)})"
            )
        return [root]
    if not root.is_dir():
        raise FileNotFoundError(f"image-to-md: input not found: {root}")
    paths = [p for p in root.iterdir() if is_image_path(p)]
    return sorted(paths, key=lambda p: p.name.lower())


def iter_image_paths_recursive(root: Path) -> list[Path]:
    """
    Collect image files under root (directory only), any nesting depth.
    Used after ZIP extraction where images may sit in subfolders.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Expected a directory: {root}")
    paths = [p for p in root.rglob("*") if is_image_path(p)]
    return sorted(paths, key=lambda p: str(p).lower())


def load_pil_rgb(path: Path):
    from PIL import Image

    img = Image.open(path)
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")
