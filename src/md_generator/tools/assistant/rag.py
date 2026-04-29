from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from .chunks import Chunk, chunk_markdown, strip_yaml_frontmatter

if TYPE_CHECKING:
    from .registry import Registry


def _tokenize(q: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", q)}


def _hash_embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic pseudo-embedding for tests / offline use without sentence-transformers."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec: list[float] = []
    for i in range(dim):
        vec.append(((h[i % len(h)] - 128) / 128.0))
    return vec


def try_chroma_retrieve(
    registry: Registry,
    query: str,
    skill_ids: list[str],
    k: int = 8,
) -> str | None:
    """Return concatenated chunk text or None if chromadb unavailable / empty."""
    try:
        import chromadb  # type: ignore
    except ImportError:
        return None

    chunks: list[Chunk] = []
    gpath = registry.global_architecture_path()
    if gpath and gpath.is_file():
        gtext = strip_yaml_frontmatter(gpath.read_text(encoding="utf-8"))
        chunks.extend(chunk_markdown(gtext, str(gpath)))
    for sid in skill_ids:
        p = registry.skill_path(sid)
        if not p or not p.is_file():
            continue
        text = strip_yaml_frontmatter(p.read_text(encoding="utf-8"))
        chunks.extend(chunk_markdown(text, str(p)))
    if not chunks:
        return None

    try:
        client = chromadb.EphemeralClient()  # type: ignore[attr-defined]
    except Exception:
        client = chromadb.Client()  # type: ignore[attr-defined]
    coll = client.create_collection("skills")
    embeddings = [_hash_embed(c.text) for c in chunks]
    coll.add(
        ids=[f"c{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[{"heading": c.heading, "path": c.source_path} for c in chunks],
    )
    qe = _hash_embed(query)
    res = coll.query(query_embeddings=[qe], n_results=min(k, len(chunks)))
    docs = (res.get("documents") or [[]])[0]
    if not docs:
        return None
    return "\n\n---\n\n".join(docs)
