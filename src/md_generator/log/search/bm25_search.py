from __future__ import annotations

import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_rank(docs: list[dict[str, object]], query: str, *, k1: float = 1.5, b: float = 0.75) -> list[tuple[str, float]]:
    q_terms = _tokenize(query)
    if not q_terms:
        return []
    N = len(docs)
    avgdl = sum(len(_tokenize(str(d.get("text", "")))) for d in docs) / max(N, 1)
    df: Counter[str] = Counter()
    for d in docs:
        terms = set(_tokenize(str(d.get("metadata", "")) + " " + str(d.get("chunk_id", ""))))
        for t in terms:
            df[t] += 1
    scores: list[tuple[str, float]] = []
    for d in docs:
        text = str(d.get("text", "")) + " " + str(d.get("chunk_id", ""))
        terms = _tokenize(text)
        tf = Counter(terms)
        dl = len(terms)
        score = 0.0
        for term in q_terms:
            n_qi = df.get(term, 0)
            idf = math.log(1 + (N - n_qi + 0.5) / (n_qi + 0.5))
            f = tf.get(term, 0)
            denom = f + k1 * (1 - b + b * dl / max(avgdl, 1))
            score += idf * (f * (k1 + 1)) / max(denom, 1e-9)
        scores.append((str(d.get("chunk_id", "")), score))
    scores.sort(key=lambda x: (-x[1], x[0]))
    return scores
