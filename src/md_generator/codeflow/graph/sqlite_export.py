"""Optional SQLite persistence for large-repo graph queries."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import networkx as nx


def export_graph_sqlite(db_path: Path, g: nx.DiGraph) -> None:
    """Write nodes and edges to SQLite (``graph.db``). Replaces existing file."""
    db_path = db_path.resolve()
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY NOT NULL, attrs_json TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE edges (src TEXT NOT NULL, tgt TEXT NOT NULL, relation TEXT, attrs_json TEXT NOT NULL)",
        )
        conn.execute("CREATE INDEX idx_edges_src ON edges(src)")
        conn.execute("CREATE INDEX idx_edges_tgt ON edges(tgt)")
        conn.execute("CREATE INDEX idx_edges_rel ON edges(relation)")
        for nid, data in g.nodes(data=True):
            payload = {k: v for k, v in dict(data).items() if k != "id"}
            conn.execute(
                "INSERT INTO nodes (id, attrs_json) VALUES (?, ?)",
                (str(nid), json.dumps(payload, default=str)),
            )
        for u, v, data in g.edges(data=True):
            d = dict(data)
            relation = str(d.get("relation", "CALLS"))
            payload = {k: v for k, v in d.items() if k != "relation"}
            conn.execute(
                "INSERT INTO edges (src, tgt, relation, attrs_json) VALUES (?, ?, ?, ?)",
                (str(u), str(v), relation, json.dumps(payload, default=str)),
            )
        conn.commit()
    finally:
        conn.close()
