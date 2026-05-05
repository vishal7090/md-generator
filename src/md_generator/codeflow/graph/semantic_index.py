"""Dense vector similarity index (cosine via dot product on L2-normalized rows)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
else:
    try:
        import numpy as np
    except ImportError as e:
        raise ImportError("semantic index requires numpy (install mdengine[codeflow] or numpy)") from e


class SemanticIndex:
    """Maps ``node_ids`` to normalized embedding rows for ``search`` / ``search_subset``."""

    __slots__ = ("node_ids", "vectors", "_id_to_row")

    def __init__(self) -> None:
        self.node_ids: list[str] = []
        self.vectors: np.ndarray | None = None
        self._id_to_row: dict[str, int] = {}

    def build(self, node_ids: list[str], vectors: np.ndarray) -> None:
        if len(node_ids) != len(vectors):
            raise ValueError("node_ids and vectors length mismatch")
        self.node_ids = list(node_ids)
        self.vectors = np.asarray(vectors, dtype=np.float64)
        if self.vectors.ndim != 2:
            raise ValueError("vectors must be 2D")
        self._id_to_row = {nid: i for i, nid in enumerate(self.node_ids)}

    def vector_for(self, node_id: str) -> np.ndarray | None:
        if self.vectors is None:
            return None
        i = self._id_to_row.get(node_id)
        if i is None:
            return None
        return self.vectors[i]

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 10,
        *,
        exclude: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        if self.vectors is None or not self.node_ids:
            return []
        q = np.asarray(query_vec, dtype=np.float64).ravel()
        sims = self.vectors @ q
        idx = np.argsort(-sims)
        out: list[tuple[str, float]] = []
        ex = exclude or set()
        for i in idx:
            nid = self.node_ids[int(i)]
            if nid in ex:
                continue
            out.append((nid, float(sims[int(i)])))
            if len(out) >= top_k:
                break
        return out

    def search_subset(
        self,
        mask_ids: set[str],
        query_vec: np.ndarray,
        top_k: int,
        *,
        exclude: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        if self.vectors is None or not self.node_ids:
            return []
        q = np.asarray(query_vec, dtype=np.float64).ravel()
        ex = exclude or set()
        scored: list[tuple[str, float]] = []
        for i, nid in enumerate(self.node_ids):
            if nid not in mask_ids or nid in ex:
                continue
            scored.append((nid, float(self.vectors[i] @ q)))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]
