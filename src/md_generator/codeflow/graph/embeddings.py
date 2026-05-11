"""Local embeddings (SentenceTransformers) with disk cache under ``.codeflow_cache/semantic``."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from md_generator.codeflow.graph import relations as rel
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_out_edges

if TYPE_CHECKING:
    import numpy as np

_MANIFEST_VERSION = 2


def _require_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as e:
        raise ImportError("embeddings require numpy") from e
    return np


def _model_slug(model_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())[:120]
    return s or "model"


def semantic_cache_dir(project_root: Path, model_id: str) -> Path:
    return project_root.resolve() / ".codeflow_cache" / "semantic" / _model_slug(model_id)


def build_embedding_text(g: CodeflowGraph, node_id: str, *, max_calls: int = 5) -> str:
    if node_id not in g:
        return ""
    d = dict(g.nodes[node_id])
    parts: list[str] = []
    mn = d.get("method_name")
    if mn:
        parts.append(str(mn))
    cn = d.get("class_name")
    if cn:
        parts.append(str(cn))
    tags = d.get("tags")
    if isinstance(tags, list) and tags:
        parts.append(" ".join(str(t) for t in tags[:12]))
    fp = d.get("file_path")
    if fp:
        parts.append(str(fp).replace("\\", "/"))
    lang = d.get("language")
    if lang:
        parts.append(str(lang))
    calls: list[str] = []
    for _u, v, _k, ed in iter_out_edges(g, node_id):
        if ed.get("relation") != rel.REL_CALLS and ed.get("kind") != rel.REL_CALLS:
            continue
        if isinstance(v, str):
            tail = v.split("::")[-1] if "::" in v else v
            calls.append(tail)
        if len(calls) >= max_calls:
            break
    if calls:
        parts.append("calls: " + ", ".join(calls))
    return " ".join(p for p in parts if p).strip()


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _encoder_backend_label() -> str:
    return "sentence_transformers"


def _library_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        import sentence_transformers as st

        out["sentence_transformers"] = str(getattr(st, "__version__", "unknown"))
    except ImportError:
        out["sentence_transformers"] = "not_installed"
    try:
        import torch

        out["torch"] = str(getattr(torch, "__version__", "unknown"))
    except ImportError:
        out["torch"] = "not_installed"
    return out


_models: dict[str, Any] = {}


def get_sentence_transformer(model_id: str):
    """Lazy-load SentenceTransformer; requires ``mdengine[codeflow-semantic]``."""
    if model_id in _models:
        return _models[model_id]
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "sentence-transformers is not installed. Install optional extra: pip install 'mdengine[codeflow-semantic]'",
        ) from e
    _models[model_id] = SentenceTransformer(model_id)
    return _models[model_id]


def embed_texts(
    texts: list[str],
    model_id: str,
    *,
    normalize_embeddings: bool = True,
) -> "np.ndarray":
    model = get_sentence_transformer(model_id)
    import numpy as np

    arr = model.encode(
        texts,
        normalize_embeddings=normalize_embeddings,
        show_progress_bar=False,
    )
    return np.asarray(arr, dtype=np.float32)


def load_cached_vectors(
    project_root: Path,
    model_id: str,
    node_ids: list[str],
    texts: list[str],
) -> tuple[Any | None, dict[str, str] | None]:
    """Return (vectors, None) if cache hit; else (None, new_hashes dict)."""
    np = _require_numpy()
    if len(node_ids) != len(texts):
        raise ValueError("node_ids and texts length mismatch")
    cdir = semantic_cache_dir(project_root, model_id)
    manifest_path = cdir / "manifest.json"
    vec_path = cdir / "vectors.f16.npy"
    hashes = {nid: _sha256_text(t) for nid, t in zip(node_ids, texts)}
    if not manifest_path.is_file() or not vec_path.is_file():
        return None, hashes
    try:
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, hashes
    if int(meta.get("manifest_version", 0)) != _MANIFEST_VERSION:
        return None, hashes
    if str(meta.get("model_id", "")) != model_id:
        return None, hashes
    old_hashes = meta.get("hashes")
    if not isinstance(old_hashes, dict):
        return None, hashes
    if {str(k): str(v) for k, v in old_hashes.items()} != hashes:
        return None, hashes
    order = meta.get("node_order")
    if not isinstance(order, list) or [str(x) for x in order] != node_ids:
        return None, hashes
    try:
        raw = np.load(vec_path)
        mat = np.asarray(raw, dtype=np.float32)
    except OSError:
        return None, hashes
    if mat.shape[0] != len(node_ids):
        return None, hashes
    return mat, None


def save_cached_vectors(
    project_root: Path,
    model_id: str,
    node_ids: list[str],
    texts: list[str],
    vectors: "np.ndarray",
) -> None:
    np = _require_numpy()
    cdir = semantic_cache_dir(project_root, model_id)
    cdir.mkdir(parents=True, exist_ok=True)
    hashes = {nid: _sha256_text(t) for nid, t in zip(node_ids, texts)}
    meta = {
        "manifest_version": _MANIFEST_VERSION,
        "model_id": model_id,
        "node_order": node_ids,
        "hashes": hashes,
        "dim": int(np.asarray(vectors).shape[1]) if np.asarray(vectors).ndim == 2 else 0,
        "encoder_backend": _encoder_backend_label(),
        "library_versions": _library_versions(),
    }
    (cdir / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    np.save(cdir / "vectors.f16.npy", np.asarray(vectors, dtype=np.float16))


def embed_nodes_cached(
    project_root: Path,
    model_id: str,
    node_ids: list[str],
    texts: list[str],
    *,
    encode_fn: Callable[[list[str], str], Any] | None = None,
) -> Any:
    """Return float32 matrix (n, dim); uses cache when texts unchanged."""
    np = _require_numpy()
    hit, miss_hashes = load_cached_vectors(project_root, model_id, node_ids, texts)
    if hit is not None:
        return np.asarray(hit, dtype=np.float32)
    enc = encode_fn or (lambda tx, mid: embed_texts(tx, mid, normalize_embeddings=True))
    vecs = enc(texts, model_id)
    vecs = np.asarray(vecs, dtype=np.float32)
    try:
        save_cached_vectors(project_root, model_id, node_ids, texts, vecs)
    except OSError:
        pass
    return vecs
