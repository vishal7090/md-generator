"""Optional SQLite persistence for large-repo graph queries."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges


def export_graph_sqlite(db_path: Path, g: CodeflowGraph) -> None:
    """Write nodes and edges to SQLite (``graph.db``). Replaces existing file."""
    db_path = db_path.resolve()
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY NOT NULL, attrs_json TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE edges (src TEXT NOT NULL, tgt TEXT NOT NULL, edge_key TEXT NOT NULL, "
            "relation TEXT, condition TEXT, confidence REAL, attrs_json TEXT NOT NULL)",
        )
        conn.execute("CREATE INDEX idx_edges_src ON edges(src)")
        conn.execute("CREATE INDEX idx_edges_tgt ON edges(tgt)")
        conn.execute("CREATE INDEX idx_edges_rel ON edges(relation)")
        conn.execute("CREATE UNIQUE INDEX idx_edges_unique ON edges(src, tgt, edge_key)")
        for nid, data in g.nodes(data=True):
            payload = {k: v for k, v in dict(data).items() if k != "id"}
            conn.execute(
                "INSERT INTO nodes (id, attrs_json) VALUES (?, ?)",
                (str(nid), json.dumps(payload, default=str)),
            )
        for u, v, ek, data in iter_multi_edges(g):
            d = dict(data)
            relation = str(d.get("relation", "CALLS"))
            cond = d.get("condition")
            conf = d.get("confidence")
            conf_f = float(conf) if conf is not None else None
            payload = {k: v for k, v in d.items() if k not in ("relation", "condition", "confidence")}
            ek_s = str(ek) if ek is not None else "0"
            conn.execute(
                "INSERT INTO edges (src, tgt, edge_key, relation, condition, confidence, attrs_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(u),
                    str(v),
                    ek_s,
                    relation,
                    str(cond) if cond is not None else None,
                    conf_f,
                    json.dumps(payload, default=str),
                ),
            )
        conn.commit()
    finally:
        conn.close()
