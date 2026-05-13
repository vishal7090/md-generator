from __future__ import annotations

import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

JUNK_NAMES = frozenset({".ds_store", "thumbs.db"})

ARCHIVE_SUFFIXES: tuple[str, ...] = (
    ".tar.gz",
    ".tar.bz2",
    ".tgz",
    ".tbz2",
    ".tar",
    ".zip",
    ".7z",
    ".rar",
)

_ARCHIVE_FORMATS_EXTRA = "archive-formats"


class ArchiveError(Exception):
    """Base error for archive extraction."""


class UnsupportedArchiveError(ArchiveError):
    """Input path is not a supported archive type."""


class MissingArchiveDependencyError(ArchiveError):
    """Optional dependency for a format is not installed."""


class ArchiveExtractionError(ArchiveError):
    """Archive could not be read or extracted."""


def should_skip_archive_member(name: str) -> bool:
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


def safe_member_path(extract_root: Path, member_name: str, jail_root: Path) -> Path | None:
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


def detect_archive_format(path: Path) -> str | None:
    name = path.name.lower()
    if name.endswith((".tar.gz", ".tgz")):
        return "tar"
    if name.endswith((".tar.bz2", ".tbz2")):
        return "tar"
    if name.endswith(".tar"):
        return "tar"
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".7z"):
        return "7z"
    if name.endswith(".rar"):
        return "rar"
    return None


def archive_filename_suffix(filename: str) -> str:
    low = filename.lower()
    for sfx in ARCHIVE_SUFFIXES:
        if low.endswith(sfx):
            return sfx
    return ".zip"


def is_supported_archive_filename(filename: str) -> bool:
    return detect_archive_format(Path(filename)) is not None


def archive_stem(path: Path) -> str:
    name = path.name.lower()
    for sfx in ARCHIVE_SUFFIXES:
        if name.endswith(sfx):
            return path.name[: -len(sfx)]
    return path.stem


def verify_archive_file(path: Path, fmt: str) -> bool:
    if fmt == "zip":
        return zipfile.is_zipfile(path)
    if fmt == "tar":
        return tarfile.is_tarfile(path)
    if fmt == "7z":
        return path.suffix.lower() == ".7z"
    if fmt == "rar":
        return path.suffix.lower() == ".rar"
    return False


def iter_nested_archive_candidates(files_root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(files_root.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file():
            continue
        fmt = detect_archive_format(path)
        if fmt is None:
            continue
        if verify_archive_file(path, fmt):
            out.append(path)
    return out


def _log_skip(verbose: bool, archive: Path, message: str) -> None:
    if verbose:
        print(f"[zip-to-md] {message} in {archive.name}", file=sys.stderr, flush=True)


def _extract_zip(archive: Path, extract_root: Path, jail_root: Path, *, verbose: bool) -> bool:
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            for name in zf.namelist():
                norm = name.replace("\\", "/")
                if should_skip_archive_member(norm):
                    continue
                dest = safe_member_path(extract_root, norm, jail_root)
                if dest is None:
                    if verbose:
                        _log_skip(verbose, archive, f"skip unsafe path {norm!r}")
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


def _extract_tar(archive: Path, extract_root: Path, jail_root: Path, *, verbose: bool) -> bool:
    try:
        with tarfile.open(archive, mode="r:*") as tf:
            for member in tf.getmembers():
                norm = member.name.replace("\\", "/")
                if should_skip_archive_member(norm):
                    continue
                if member.isdir() or norm.endswith("/"):
                    dest = safe_member_path(extract_root, norm.rstrip("/"), jail_root)
                    if dest is not None:
                        dest.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    continue
                dest = safe_member_path(extract_root, norm, jail_root)
                if dest is None:
                    if verbose:
                        _log_skip(verbose, archive, f"skip unsafe path {norm!r}")
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(member)
                if src is None:
                    continue
                with src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    except (tarfile.TarError, OSError) as e:
        if verbose:
            print(f"[zip-to-md] bad tar {archive}: {e}", file=sys.stderr, flush=True)
        return False
    return True


def _extract_7z(archive: Path, extract_root: Path, jail_root: Path, *, verbose: bool) -> bool:
    try:
        import py7zr
    except ImportError as e:
        raise MissingArchiveDependencyError(
            f"7z extraction requires py7zr (install mdengine[{_ARCHIVE_FORMATS_EXTRA}]): {e}"
        ) from e
    try:
        with py7zr.SevenZipFile(archive, mode="r") as zf:
            payload = zf.read()
        for name, bio in payload.items():
            norm = name.replace("\\", "/")
            if should_skip_archive_member(norm):
                continue
            if norm.endswith("/"):
                dest = safe_member_path(extract_root, norm.rstrip("/"), jail_root)
                if dest is not None:
                    dest.mkdir(parents=True, exist_ok=True)
                continue
            dest = safe_member_path(extract_root, norm, jail_root)
            if dest is None:
                if verbose:
                    _log_skip(verbose, archive, f"skip unsafe path {norm!r}")
                continue
            if bio is None:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = bio.read() if hasattr(bio, "read") else bio
            dest.write_bytes(data)
    except Exception as e:
        if verbose:
            print(f"[zip-to-md] bad 7z {archive}: {e}", file=sys.stderr, flush=True)
        return False
    return True


def _extract_rar(archive: Path, extract_root: Path, jail_root: Path, *, verbose: bool) -> bool:
    try:
        import patoolib
    except ImportError as e:
        raise MissingArchiveDependencyError(
            f"RAR extraction requires patoolib (install mdengine[{_ARCHIVE_FORMATS_EXTRA}]): {e}"
        ) from e
    try:
        with tempfile.TemporaryDirectory(prefix="archive-rar-") as td:
            patoolib.extract_archive(str(archive), outdir=td, verbosity=-1)
            root = Path(td)
            for src in sorted(root.rglob("*")):
                if not src.is_file():
                    continue
                rel = src.relative_to(root).as_posix()
                if should_skip_archive_member(rel):
                    continue
                dest = safe_member_path(extract_root, rel, jail_root)
                if dest is None:
                    if verbose:
                        _log_skip(verbose, archive, f"skip unsafe path {rel!r}")
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
    except Exception as e:
        if verbose:
            print(
                f"[zip-to-md] bad rar {archive}: {e} (patool may need unrar/rar on PATH)",
                file=sys.stderr,
                flush=True,
            )
        return False
    return True


def extract_archive_to_dir(
    archive: Path,
    extract_root: Path,
    jail_root: Path,
    *,
    verbose: bool,
) -> bool:
    fmt = detect_archive_format(archive)
    if fmt is None:
        return False
    if fmt == "zip":
        return _extract_zip(archive, extract_root, jail_root, verbose=verbose)
    if fmt == "tar":
        return _extract_tar(archive, extract_root, jail_root, verbose=verbose)
    if fmt == "7z":
        return _extract_7z(archive, extract_root, jail_root, verbose=verbose)
    if fmt == "rar":
        return _extract_rar(archive, extract_root, jail_root, verbose=verbose)
    return False


def extract_archive(
    archive: Path,
    extract_root: Path,
    jail_root: Path,
    *,
    verbose: bool,
) -> None:
    fmt = detect_archive_format(archive)
    if fmt is None:
        raise UnsupportedArchiveError(f"Unsupported archive type: {archive.name}")
    if not verify_archive_file(archive, fmt):
        raise ArchiveExtractionError(f"File does not look like a valid {fmt} archive: {archive}")
    try:
        ok = extract_archive_to_dir(archive, extract_root, jail_root, verbose=verbose)
    except MissingArchiveDependencyError:
        raise
    except Exception as e:
        raise ArchiveExtractionError(f"Failed to extract {archive.name}: {e}") from e
    if not ok:
        raise ArchiveExtractionError(f"Failed to extract {archive.name}")
