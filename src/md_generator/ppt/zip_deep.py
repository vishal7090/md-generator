from __future__ import annotations

import zipfile
from pathlib import Path


def unpack_zip_tree(
    zip_path: Path,
    dest_dir: Path,
    *,
    current_depth: int,
    max_depth: int,
    verbose: bool = False,
) -> None:
    """Unpack zip_path into dest_dir; recurse into nested zips up to max_depth."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    if current_depth >= max_depth:
        return
    for p in list(dest_dir.rglob("*")):
        if not p.is_file():
            continue
        try:
            if zipfile.is_zipfile(p):
                sub = dest_dir / f"{p.stem}_unpacked"
                if verbose:
                    print(f"[zip] nested {p.name} -> {sub}", flush=True)
                unpack_zip_tree(p, sub, current_depth=current_depth + 1, max_depth=max_depth, verbose=verbose)
        except zipfile.BadZipFile:
            continue
