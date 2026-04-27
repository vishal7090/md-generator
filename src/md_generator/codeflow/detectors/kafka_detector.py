"""Kafka / messaging listener hints (best-effort)."""

from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.models.ir import EntryKind, EntryRecord


def detect_kafka_entries_java_source(path: Path, project_root: Path) -> list[EntryRecord]:
    """TODO: Full topic graph linking (producer → topic → consumer) needs runtime/config."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if "@KafkaListener" not in text and "KafkaListener" not in text:
        return []
    key = path.resolve().relative_to(project_root.resolve()).as_posix()
    out: list[EntryRecord] = []
    try:
        import javalang

        tree = javalang.parse.parse(text)
    except Exception:
        return out

    for t in tree.types or []:
        cls_name = getattr(t, "name", "")
        for m in getattr(t, "methods", None) or []:
            ann_blob = " ".join(str(getattr(a, "name", a)) for a in (getattr(m, "annotations", None) or []))
            if "KafkaListener" in ann_blob:
                sym = f"{key}::{cls_name}.{m.name}"
                pos = getattr(m, "position", None)
                line = int(getattr(pos, "line", 0) or 0) if pos else 0
                out.append(
                    EntryRecord(
                        symbol_id=sym,
                        kind=EntryKind.KAFKA,
                        label="@KafkaListener",
                        file_path=str(path.resolve()),
                        line=line,
                    )
                )
    return out


def detect_kafka_entries(path: Path, project_root: Path) -> list[EntryRecord]:
    if path.suffix.lower() == ".java":
        return detect_kafka_entries_java_source(path, project_root)
    return []
