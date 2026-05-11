from __future__ import annotations

from typing import Any


def tfidf_matrix(texts: list[str], *, max_features: int) -> tuple[Any, Any]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError as e:
        raise ImportError("log-cluster extra requires scikit-learn") from e
    vec = TfidfVectorizer(max_features=max_features, stop_words="english")
    X = vec.fit_transform(texts)
    return vec, X
