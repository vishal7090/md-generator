from __future__ import annotations

from md_generator.log.search.bm25_search import bm25_rank
from md_generator.log.search.vector_search import vector_search


def hybrid_search(docs: list[dict[str, object]], query: str) -> list[tuple[str, float]]:
    bm = {cid: s for cid, s in bm25_rank(docs, query)}
    vec = {cid: s for cid, s in vector_search(docs, query)}
    keys = set(bm) | set(vec)
    merged = [(k, 0.6 * bm.get(k, 0.0) + 0.4 * vec.get(k, 0.0)) for k in keys]
    merged.sort(key=lambda x: (-x[1], x[0]))
    return merged
