from __future__ import annotations

from pathlib import Path

from md_generator.log.search.hybrid_search import hybrid_search
from md_generator.log.search.search_index import load_index


def run_search(query: str, index_root: Path, *, limit: int = 10) -> list[tuple[str, float]]:
    docs = load_index(index_root)
    if not docs:
        return []
    # enrich docs with text from chunk files when missing
    enriched: list[dict[str, object]] = []
    for row in docs:
        d = dict(row)
        if "text" not in d:
            rel = str(d.get("path", ""))
            p = index_root / rel
            if p.is_file():
                d["text"] = p.read_text(encoding="utf-8")[:8000]
            else:
                d["text"] = ""
        enriched.append(d)
    return hybrid_search(enriched, query)[:limit]
