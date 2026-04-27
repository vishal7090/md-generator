from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from md_generator.codeflow.lang_dispatch import (
    MIXED_LANG_KEYS,
    extensions_for_languages,
    normalize_language_filter,
)


@dataclass(frozen=True, slots=True)
class LoadedWorkspace:
    root: Path
    cleanup_dir: Path | None = None

    def close(self) -> None:
        if self.cleanup_dir and self.cleanup_dir.exists():
            shutil.rmtree(self.cleanup_dir, ignore_errors=True)


def _extract_zip(zip_path: Path) -> Path:
    td = Path(tempfile.mkdtemp(prefix="codeflow-zip-"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(td)
    return td


def load_workspace(
    *,
    path: Path,
) -> LoadedWorkspace:
    """Return a project root. If ``path`` is a ``.zip``, extract to a temp directory."""
    p = path.expanduser().resolve()
    if p.is_file() and p.suffix.lower() == ".zip":
        td = _extract_zip(p)
        return LoadedWorkspace(root=td, cleanup_dir=td)
    if p.is_file():
        return LoadedWorkspace(root=p.parent, cleanup_dir=None)
    return LoadedWorkspace(root=p, cleanup_dir=None)


def collect_source_files(root: Path, languages: str) -> list[Path]:
    allowed = normalize_language_filter(languages)
    exts = extensions_for_languages(allowed)
    if not exts:
        exts = extensions_for_languages(MIXED_LANG_KEYS)
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if "node_modules" in p.parts or ".git" in p.parts or "vendor" in p.parts:
            continue
        out.append(p)
    return sorted(out)


def source_file_extensions() -> frozenset[str]:
    """All extensions the tool may treat as source when ``languages=mixed``."""
    return frozenset(extensions_for_languages(MIXED_LANG_KEYS))
