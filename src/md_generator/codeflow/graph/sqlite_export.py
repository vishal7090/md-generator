"""Optional SQLite persistence for large-repo graph queries."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges


def _pragma_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def _ensure_scan_columns(conn: sqlite3.Connection) -> None:
    for table, col, decl in (
        ("nodes", "first_seen_scan_id", "INTEGER NOT NULL DEFAULT 0"),
        ("nodes", "last_seen_scan_id", "INTEGER NOT NULL DEFAULT 0"),
        ("edges", "first_seen_scan_id", "INTEGER NOT NULL DEFAULT 0"),
        ("edges", "last_seen_scan_id", "INTEGER NOT NULL DEFAULT 0"),
    ):
        cols = _pragma_columns(conn, table)
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def export_graph_sqlite_incremental(
    db_path: Path,
    g: CodeflowGraph,
    *,
    project_key: str,
    prune_missing: bool = False,
) -> int:
    """Upsert nodes/edges and record a scan row. Returns ``scan_id``.

    If ``prune_missing``, removes nodes/edges not touched in this scan (by ``last_seen_scan_id``).
    """
    db_path = db_path.resolve()
    new_file = not db_path.exists()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS scans (scan_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "started_at REAL NOT NULL, project_key TEXT NOT NULL)",
        )
        if new_file:
            conn.execute(
                "CREATE TABLE nodes (id TEXT PRIMARY KEY NOT NULL, attrs_json TEXT NOT NULL, "
                "first_seen_scan_id INTEGER NOT NULL DEFAULT 0, last_seen_scan_id INTEGER NOT NULL DEFAULT 0)",
            )
            conn.execute(
                "CREATE TABLE edges (src TEXT NOT NULL, tgt TEXT NOT NULL, edge_key TEXT NOT NULL, "
                "relation TEXT, condition TEXT, confidence REAL, attrs_json TEXT NOT NULL, "
                "first_seen_scan_id INTEGER NOT NULL DEFAULT 0, last_seen_scan_id INTEGER NOT NULL DEFAULT 0)",
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(tgt)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relation)")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique ON edges(src, tgt, edge_key)",
            )
        else:
            _ensure_scan_columns(conn)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique ON edges(src, tgt, edge_key)",
            )
        now = time.time()
        cur = conn.execute(
            "INSERT INTO scans (started_at, project_key) VALUES (?, ?)",
            (now, str(project_key)),
        )
        sid = int(cur.lastrowid)
        for nid, data in g.nodes(data=True):
            payload = {k: v for k, v in dict(data).items() if k != "id"}
            js = json.dumps(payload, default=str)
            conn.execute(
                """
                INSERT INTO nodes (id, attrs_json, first_seen_scan_id, last_seen_scan_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  attrs_json = excluded.attrs_json,
                  last_seen_scan_id = excluded.last_seen_scan_id
                """,
                (str(nid), js, sid, sid),
            )
            conn.execute(
                "UPDATE nodes SET first_seen_scan_id = ? WHERE id = ? AND first_seen_scan_id = 0",
                (sid, str(nid)),
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
                """
                INSERT INTO edges (src, tgt, edge_key, relation, condition, confidence, attrs_json,
                  first_seen_scan_id, last_seen_scan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(src, tgt, edge_key) DO UPDATE SET
                  relation = excluded.relation,
                  condition = excluded.condition,
                  confidence = excluded.confidence,
                  attrs_json = excluded.attrs_json,
                  last_seen_scan_id = excluded.last_seen_scan_id
                """,
                (
                    str(u),
                    str(v),
                    ek_s,
                    relation,
                    str(cond) if cond is not None else None,
                    conf_f,
                    json.dumps(payload, default=str),
                    sid,
                    sid,
                ),
            )
            conn.execute(
                "UPDATE edges SET first_seen_scan_id = ? WHERE src = ? AND tgt = ? AND edge_key = ? "
                "AND first_seen_scan_id = 0",
                (sid, str(u), str(v), ek_s),
            )
        if prune_missing:
            conn.execute("DELETE FROM edges WHERE last_seen_scan_id != ?", (sid,))
            conn.execute("DELETE FROM nodes WHERE last_seen_scan_id != ?", (sid,))
        conn.commit()
        return sid
    finally:
        conn.close()


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
