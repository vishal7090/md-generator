from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import olefile

from md_generator.ppt.zip_deep import unpack_zip_tree


def _decode_ole10native_payload(data: bytes) -> tuple[bytes | None, str | None]:
    """
    Best-effort Ole10Native parse: returns (payload_bytes, suggested_filename).
    See MS-OLEDS / common Office embedding layout.
    """
    if len(data) < 10:
        return None, None
    # Try to find a plausible filename (ASCII segment)
    try:
        # Heuristic: search for .zip, .docx, .bin markers
        for m in re.finditer(rb"[\x20-\x7e]{1,200}\.(zip|docx|xlsx|pdf|txt|bin|xml)", data):
            fn = m.group(0).decode("ascii", errors="ignore")
            start = m.end()
            # payload often follows filename + null padding
            tail = data[start:]
            # trim leading zeros
            j = 0
            while j < len(tail) and tail[j] == 0:
                j += 1
            payload = tail[j:] if j < len(tail) else None
            return payload, fn
    except Exception:
        pass
    # Fallback: return tail after first null doublet
    null2 = data.find(b"\x00\x00", 4)
    if null2 > 0:
        tail = data[null2 + 2 :]
        j = 0
        while j < len(tail) and tail[j] == 0:
            j += 1
        return (tail[j:] if j < len(tail) else None), None
    return None, None


def _streams_decodable_text(ole: olefile.OleFileIO, max_chars: int = 200_000) -> str | None:
    parts: list[str] = []
    for entry in ole.listdir():
        name = "/".join(entry) if isinstance(entry, (list, tuple)) else str(entry)
        try:
            if ole.get_type(name) != olefile.STGTY_STREAM:
                continue
            raw = ole.openstream(entry).read()
            text = raw.decode("utf-8", errors="ignore")
            if sum(1 for c in text if c.isprintable() or c in "\n\r\t") / max(len(text), 1) > 0.85:
                cleaned = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
                if len(cleaned.strip()) > 20:
                    parts.append(f"### Stream: {name}\n\n{cleaned[: max_chars // max(len(parts), 1)]}")
        except Exception:
            continue
    if not parts:
        return None
    return "\n\n".join(parts)[:max_chars]


def extract_embedding_file(
    src: Path,
    dest_root: Path,
    assets_dir: Path,
    *,
    slide_idx: int,
    obj_idx: int,
    max_unpack_depth: int,
    verbose: bool,
) -> dict[str, Any]:
    """Extract one ppt/embeddings/* member; return manifest record."""
    rel_dest = dest_root / f"slide_{slide_idx}_obj_{obj_idx}"
    rel_dest.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "source": src.name,
        "slide": slide_idx,
        "object_index": obj_idx,
        "ole_extraction": {"status": "failed", "paths": []},
    }

    def rel(p: Path) -> str:
        return str(p.resolve().relative_to(assets_dir.resolve()))

    if zipfile.is_zipfile(src):
        record["ole_extraction"]["status"] = "zip_in_ole"
        unpack_dir = rel_dest / f"slide_{slide_idx}_obj_{obj_idx}_native_payload_unpacked"
        unpack_zip_tree(src, unpack_dir, current_depth=0, max_depth=max_unpack_depth, verbose=verbose)
        record["ole_extraction"]["paths"].append(rel(unpack_dir))
        if verbose:
            print(f"[embed] zip {src.name} -> {unpack_dir}", flush=True)
        return record

    if olefile.isOleFile(src):
        try:
            ole = olefile.OleFileIO(str(src))
        except Exception:
            record["ole_extraction"]["status"] = "failed"
            return record
        native_entry = None
        for entry in ole.listdir():
            label = entry[0] if isinstance(entry, (list, tuple)) else str(entry)
            if "Ole10Native" in label or label.startswith("\x01Ole"):
                native_entry = entry
                break
        if native_entry is not None:
            try:
                raw = ole.openstream(native_entry).read()
            except Exception:
                raw = b""
            payload, fn = _decode_ole10native_payload(raw)
            if payload:
                ext = Path(fn).suffix if fn else ".bin"
                safe_fn = Path(fn).name if fn else f"payload{ext}"
                safe_fn = re.sub(r"[^\w.\-]+", "_", safe_fn)[:120] or "payload.bin"
                pay_path = rel_dest / f"slide_{slide_idx}_obj_{obj_idx}_payload" / safe_fn
                pay_path.parent.mkdir(parents=True, exist_ok=True)
                pay_path.write_bytes(payload)
                record["ole_extraction"]["status"] = "ole10native"
                record["ole_extraction"]["paths"].append(rel(pay_path))
                if zipfile.is_zipfile(pay_path):
                    unpack_dir = rel_dest / f"slide_{slide_idx}_obj_{obj_idx}_native_payload_unpacked"
                    unpack_zip_tree(
                        pay_path,
                        unpack_dir,
                        current_depth=0,
                        max_depth=max_unpack_depth,
                        verbose=verbose,
                    )
                    record["ole_extraction"]["status"] = "zip_in_ole"
                    record["ole_extraction"]["paths"].append(rel(unpack_dir))
                ole.close()
                return record
        # stream text fallback
        text = _streams_decodable_text(ole)
        ole.close()
        if text:
            txt_path = rel_dest / f"slide_{slide_idx}_obj_{obj_idx}_ole_stream_text.txt"
            txt_path.write_text(text, encoding="utf-8")
            record["ole_extraction"]["status"] = "stream_text_fallback"
            record["ole_extraction"]["paths"].append(rel(txt_path))
            return record
        record["ole_extraction"]["status"] = "failed"
        return record

    # Unknown binary: copy raw
    raw_dest = rel_dest / f"slide_{slide_idx}_obj_{obj_idx}_raw{src.suffix or '.bin'}"
    raw_dest.write_bytes(src.read_bytes())
    record["ole_extraction"]["status"] = "failed"
    record["ole_extraction"]["paths"].append(rel(raw_dest))
    return record


def extract_all_embeddings(
    pptx_path: Path,
    assets_dir: Path,
    options,
    manifest: list[dict[str, Any]],
    *,
    verbose: bool = False,
) -> None:
    """Extract ppt/embeddings/* into assets/other/embedded when enabled."""
    if not options.extract_embedded_deep:
        return
    embedded_root = assets_dir / "other" / "embedded"
    embedded_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pptx_path, "r") as zf:
        emb = sorted(n for n in zf.namelist() if n.startswith("ppt/embeddings/") and not n.endswith("/"))
        for i, name in enumerate(emb, start=1):
            tmp = embedded_root / f"_tmp_{i}_{Path(name).name}"
            tmp.write_bytes(zf.read(name))
            try:
                rec = extract_embedding_file(
                    tmp,
                    embedded_root,
                    assets_dir,
                    slide_idx=0,
                    obj_idx=i,
                    max_unpack_depth=options.max_unpack_depth,
                    verbose=verbose,
                )
                manifest.append(rec)
            finally:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
