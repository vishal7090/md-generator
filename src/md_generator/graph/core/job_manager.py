from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from md_generator.graph.core.extractor import extract_to_markdown
from md_generator.graph.core.models import JobStatus
from md_generator.graph.core.run_config import GraphRunConfig, VizConfig, graph_config_to_jsonable

logger = logging.getLogger(__name__)


@dataclass
class GraphJobRecord:
    job_id: str
    status: str
    progress: int
    current: str
    workspace: str
    zip_path: str | None
    error: str | None
    created_at: float
    updated_at: float

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "current": self.current,
            "workspace": self.workspace,
            "zip_path": self.zip_path,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _zip_dir(src_dir: Path, dest_zip: Path) -> None:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src_dir.rglob("*")):
            if p.is_file():
                arc = p.relative_to(src_dir).as_posix()
                zf.write(p, arc)


class GraphJobManager:
    def __init__(
        self,
        *,
        sqlite_path: str | Path | None = None,
        workspace_root: Path | None = None,
        in_memory: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._root = Path(workspace_root) if workspace_root else None
        if in_memory:
            self._conn: sqlite3.Connection | None = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            path = Path(sqlite_path or _default_sqlite_path())
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        assert self._conn is not None
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                current TEXT NOT NULL DEFAULT '',
                workspace TEXT NOT NULL,
                zip_path TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                config_json TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def create_job(self, cfg: GraphRunConfig) -> GraphJobRecord:
        jid = str(uuid.uuid4())
        base = self._root or Path.cwd() / "graph-md-jobs"
        ws = (base / jid).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cfg_dump = json.dumps(graph_config_to_jsonable(cfg.normalized()), sort_keys=True)
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (job_id, status, progress, current, workspace, zip_path, error, created_at, updated_at, config_json)
                VALUES (?, ?, 0, '', ?, NULL, NULL, ?, ?, ?)
                """,
                (jid, JobStatus.PENDING.value, str(ws), now, now, cfg_dump),
            )
            self._conn.commit()
        return self.get(jid)  # type: ignore[return-value]

    def get(self, job_id: str) -> GraphJobRecord | None:
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_record(row)

    def update_progress(self, job_id: str, progress: int, current: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET progress = ?, current = ?, updated_at = ? WHERE job_id = ?",
                (progress, current, now, job_id),
            )
            self._conn.commit()

    def mark_running(self, job_id: str) -> None:
        self._set_status(job_id, JobStatus.RUNNING.value)

    def mark_completed(self, job_id: str, zip_path: Path | None) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, progress = 100, zip_path = ?, updated_at = ?, current = ? WHERE job_id = ?",
                (JobStatus.COMPLETED.value, str(zip_path) if zip_path else None, now, "completed", job_id),
            )
            self._conn.commit()

    def mark_failed(self, job_id: str, err: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?, current = ? WHERE job_id = ?",
                (JobStatus.FAILED.value, err[:8000], now, "failed", job_id),
            )
            self._conn.commit()

    def _set_status(self, job_id: str, status: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, now, job_id),
            )
            self._conn.commit()

    def load_config(self, job_id: str) -> GraphRunConfig | None:
        rec = self.get(job_id)
        if not rec:
            return None
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute("SELECT config_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["config_json"])
        return _config_from_jsonable(data)

    def run_job_thread(self, job_id: str) -> None:
        def target() -> None:
            try:
                self.mark_running(job_id)
                cfg = self.load_config(job_id)
                if not cfg:
                    self.mark_failed(job_id, "missing config")
                    return
                rec = self.get(job_id)
                if not rec:
                    return
                ws = Path(rec.workspace)
                out = ws / "markdown"

                def on_progress(p: int, cur: str) -> None:
                    self.update_progress(job_id, p, cur)

                n_files = [0]

                def on_file(_p: Path) -> None:
                    n_files[0] += 1
                    self.update_progress(job_id, min(95, 30 + n_files[0]), "file_generated")

                cfg_run = cfg.with_output(out)
                extract_to_markdown(cfg_run, on_progress=on_progress, on_file=on_file)
                zpath = ws / "output.zip"
                _zip_dir(out, zpath)
                optional_json = ws / "job.json"
                optional_json.write_text(
                    json.dumps({"job_id": job_id, "config": graph_config_to_jsonable(cfg)}, indent=2),
                    encoding="utf-8",
                )
                self.mark_completed(job_id, zpath)
            except Exception as e:
                logger.exception("job %s failed", job_id)
                self.mark_failed(job_id, str(e))

        threading.Thread(target=target, daemon=True).start()

    def remove_after_download(self, job_id: str) -> None:
        rec = self.get(job_id)
        if not rec:
            return
        ws = Path(rec.workspace)
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)
        assert self._conn is not None
        with self._lock:
            self._conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            self._conn.commit()


def _default_sqlite_path() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / "mdengine-graph-jobs" / "jobs.sqlite"


def _config_from_jsonable(data: dict[str, Any]) -> GraphRunConfig:
    gf = data.get("graph_file")
    return GraphRunConfig(
        source=str(data["source"]),
        uri=str(data.get("uri", "")),
        user=str(data.get("user", "")),
        password=str(data.get("password", "")),
        graph_file=Path(str(gf)) if gf else None,
        neo4j_id_mode=str(data.get("neo4j_id_mode", "element_id")),
        neo4j_database=data.get("neo4j_database"),
        neo4j_page_size=int(data.get("neo4j_page_size", 500)),
        connection_timeout_s=float(data.get("connection_timeout_s", 30.0)),
        depth=int(data.get("depth", 0)),
        start_node=data.get("start_node"),
        max_nodes=int(data.get("max_nodes", 10_000)),
        max_edges=int(data.get("max_edges", 50_000)),
        output_path=Path(str(data["output_path"])),
        split_files=bool(data.get("split_files", True)),
        combine_markdown=bool(data.get("combine_markdown", True)),
        workers=int(data.get("workers", 4)),
        viz=VizConfig(
            enabled=bool(data.get("viz_enabled", False)),
            mermaid=bool(data.get("viz_mermaid", True)),
            formats=tuple(str(x) for x in (data.get("viz_formats") or ["png", "svg"])),
        ),
    ).normalized()


def _row_to_record(row: sqlite3.Row) -> GraphJobRecord:
    return GraphJobRecord(
        job_id=str(row["job_id"]),
        status=str(row["status"]),
        progress=int(row["progress"]),
        current=str(row["current"] or ""),
        workspace=str(row["workspace"]),
        zip_path=str(row["zip_path"]) if row["zip_path"] else None,
        error=str(row["error"]) if row["error"] else None,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
