from __future__ import annotations

from md_generator.log.search.bm25_search import bm25_rank


def vector_search(docs: list[dict[str, object]], query: str) -> list[tuple[str, float]]:
    # Metadata-only fallback: reuse BM25 until vectors are exported.
    return bm25_rank(docs, query)
