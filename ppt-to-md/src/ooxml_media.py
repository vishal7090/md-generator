from __future__ import annotations

import re
import zipfile
from pathlib import Path


def _ppt_media_path_for_target(target: str, pptx_zip: zipfile.ZipFile) -> str | None:
    """Map a relationship Target string to an existing zip member under ppt/media/."""
    t = target.replace("\\", "/").strip()
    if "media/" in t:
        after = t.split("media/", 1)[1]
        after = after.split("?")[0]
        candidate = "ppt/media/" + after.lstrip("/")
        if candidate in pptx_zip.namelist():
            return candidate
        # basename only
        base = Path(after).name
        cand2 = "ppt/media/" + base
        if cand2 in pptx_zip.namelist():
            return cand2
    return None


def collect_referenced_media_paths(pptx_zip: zipfile.ZipFile) -> set[str]:
    referenced: set[str] = set()
    for name in pptx_zip.namelist():
        if not name.endswith(".rels"):
            continue
        try:
            text = pptx_zip.read(name).decode("utf-8", errors="ignore")
        except KeyError:
            continue
        for m in re.finditer(
            r'Relationship[^>]+Target="([^"]+)"',
            text,
            re.I,
        ):
            p = _ppt_media_path_for_target(m.group(1), pptx_zip)
            if p:
                referenced.add(p)
    return referenced


def list_ppt_media_members(pptx_zip: zipfile.ZipFile) -> list[str]:
    return sorted(n for n in pptx_zip.namelist() if n.startswith("ppt/media/") and not n.endswith("/"))


def copy_media_bundle(
    pptx_zip: zipfile.ZipFile,
    dest_media_dir: Path,
    *,
    verbose: bool = False,
) -> tuple[list[str], list[str]]:
    """
    Copy ppt/media into dest_media_dir.
    Returns (linked_basenames_written, orphan_basenames_written).
    """
    dest_media_dir.mkdir(parents=True, exist_ok=True)
    referenced = collect_referenced_media_paths(pptx_zip)
    members = list_ppt_media_members(pptx_zip)
    linked: list[str] = []
    orphans: list[str] = []
    used_names: set[str] = set()

    def unique_name(want: str) -> str:
        if want not in used_names:
            used_names.add(want)
            return want
        stem = Path(want).stem
        suf = Path(want).suffix
        i = 2
        while True:
            cand = f"{stem}_{i}{suf}"
            if cand not in used_names:
                used_names.add(cand)
                return cand
            i += 1

    for member in members:
        base = Path(member).name
        is_ref = member in referenced
        dest_base = base if is_ref else f"orphan_{base}"
        dest_base = unique_name(dest_base)
        out = dest_media_dir / dest_base
        out.write_bytes(pptx_zip.read(member))
        if is_ref:
            linked.append(dest_base)
        else:
            orphans.append(dest_base)
        if verbose:
            print(f"[media] {member} -> {out.name}", flush=True)

    return linked, orphans
