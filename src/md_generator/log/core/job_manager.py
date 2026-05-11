from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.extractor import extract_to_markdown
from md_generator.log.core.run_config import jsonable_to_log_config, log_config_to_jsonable

logger = logging.getLogger(__name__)


class LogJobStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class LogJobRecord:
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


class LogJobManager:
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
            CREATE TABLE IF NOT EXISTS log_jobs (
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

    def create_job(self, cfg: LogRunConfig) -> LogJobRecord:
        jid = str(uuid.uuid4())
        base = self._root or Path.cwd() / "log-md-jobs"
        ws = (base / jid).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        cfg_run = replace(cfg, output=replace(cfg.output, path=str(ws / "markdown")))
        now = time.time()
        cfg_dump = json.dumps(log_config_to_jsonable(cfg_run), sort_keys=True, default=str)
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO log_jobs (job_id, status, progress, current, workspace, zip_path, error, created_at, updated_at, config_json)
                VALUES (?, ?, 0, '', ?, NULL, NULL, ?, ?, ?)
                """,
                (jid, LogJobStatus.PENDING, str(ws), now, now, cfg_dump),
            )
            self._conn.commit()
        return self.get(jid)  # type: ignore[return-value]

    def create_upload_job(self, log_bytes: bytes, cfg_template: LogRunConfig, *, filename: str = "upload.log") -> LogJobRecord:
        jid = str(uuid.uuid4())
        base = self._root or Path.cwd() / "log-md-jobs"
        ws = (base / jid).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        log_path = ws / filename
        log_path.write_bytes(log_bytes)
        cfg = replace(
            cfg_template,
            input=replace(cfg_template.input, paths=[str(log_path)]),
            output=replace(cfg_template.output, path=str(ws / "markdown")),
        )
        now = time.time()
        cfg_dump = json.dumps(log_config_to_jsonable(cfg), sort_keys=True, default=str)
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO log_jobs (job_id, status, progress, current, workspace, zip_path, error, created_at, updated_at, config_json)
                VALUES (?, ?, 0, '', ?, NULL, NULL, ?, ?, ?)
                """,
                (jid, LogJobStatus.PENDING, str(ws), now, now, cfg_dump),
            )
            self._conn.commit()
        return self.get(jid)  # type: ignore[return-value]

    def get(self, job_id: str) -> LogJobRecord | None:
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute("SELECT * FROM log_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_record(row)

    def update_progress(self, job_id: str, progress: int, current: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE log_jobs SET progress = ?, current = ?, updated_at = ? WHERE job_id = ?",
                (progress, current, now, job_id),
            )
            self._conn.commit()

    def mark_running(self, job_id: str) -> None:
        self._set_status(job_id, LogJobStatus.RUNNING)

    def mark_completed(self, job_id: str, zip_path: Path | None) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE log_jobs SET status = ?, progress = 100, zip_path = ?, updated_at = ?, current = ? WHERE job_id = ?",
                (LogJobStatus.COMPLETED, str(zip_path) if zip_path else None, now, "completed", job_id),
            )
            self._conn.commit()

    def mark_failed(self, job_id: str, err: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE log_jobs SET status = ?, error = ?, updated_at = ?, current = ? WHERE job_id = ?",
                (LogJobStatus.FAILED, err[:8000], now, "failed", job_id),
            )
            self._conn.commit()

    def _set_status(self, job_id: str, status: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE log_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (status, now, job_id),
            )
            self._conn.commit()

    def load_config(self, job_id: str) -> LogRunConfig | None:
        rec = self.get(job_id)
        if not rec:
            return None
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute(
                "SELECT config_json FROM log_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        data = json.loads(row["config_json"])
        return jsonable_to_log_config(data).normalized()

    def run_job_thread(self, job_id: str) -> None:
        def target() -> None:
            try:
                self.mark_running(job_id)
                self.update_progress(job_id, 10, "log:parse")
                cfg = self.load_config(job_id)
                if not cfg:
                    self.mark_failed(job_id, "missing config")
                    return
                rec = self.get(job_id)
                if not rec:
                    return
                ws = Path(rec.workspace)
                extract_to_markdown(cfg)
                self.update_progress(job_id, 90, "log:zip")
                zpath = ws / "output.zip"
                out_root = cfg.output_path()
                _zip_dir(out_root, zpath)
                self.mark_completed(job_id, zpath)
            except Exception as e:
                logger.exception("log job %s failed", job_id)
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
            self._conn.execute("DELETE FROM log_jobs WHERE job_id = ?", (job_id,))
            self._conn.commit()


def _default_sqlite_path() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / "mdengine-log-jobs" / "jobs.sqlite"


def _row_to_record(row: sqlite3.Row) -> LogJobRecord:
    return LogJobRecord(
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
