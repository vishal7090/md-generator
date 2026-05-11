from __future__ import annotations

from typing import Any


def run_kmeans(X: Any, *, n_clusters: int, random_state: int) -> Any:
    try:
        from sklearn.cluster import KMeans
    except ImportError as e:
        raise ImportError("log-cluster extra requires scikit-learn") from e
    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    return km.fit_predict(X)
