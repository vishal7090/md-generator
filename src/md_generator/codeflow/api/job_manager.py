from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from md_generator.codeflow.api.schemas import scan_config_dump, scan_config_load
from md_generator.codeflow.core.extractor import run_scan
from md_generator.codeflow.core.run_config import ScanConfig
from md_generator.codeflow.ingestion.loader import LoadedWorkspace


@dataclass
class CodeflowJobRecord:
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


class CodeflowJobManager:
    """SQLite-backed job store (same pattern as db-to-md ``JobManager``)."""

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
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
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

    def create_zip_job(self, zip_bytes: bytes, cfg_template: ScanConfig) -> CodeflowJobRecord:
        jid = str(uuid.uuid4())
        base = self._root or Path.cwd() / "codeflow-jobs"
        ws = (base / jid).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        src = ws / "src"
        src.mkdir(parents=True, exist_ok=True)
        raw_zip = ws / "upload.zip"
        raw_zip.write_bytes(zip_bytes)
        with zipfile.ZipFile(raw_zip, "r") as zf:
            zf.extractall(src)

        out = ws / "out"
        cfg = ScanConfig(
            project_root=src,
            output_path=out,
            formats=cfg_template.formats,
            depth=cfg_template.depth,
            languages=cfg_template.languages,
            entry=cfg_template.entry,
            include=cfg_template.include,
            exclude=cfg_template.exclude,
            include_internal=cfg_template.include_internal,
            async_mode=cfg_template.async_mode,
            jobs=True,
            runtime=cfg_template.runtime,
            paths_override=cfg_template.paths_override,
            business_rules=cfg_template.business_rules,
            business_rules_sql=cfg_template.business_rules_sql,
            business_rules_combined=cfg_template.business_rules_combined,
            entry_fallback=cfg_template.entry_fallback,
            entry_fallback_max=cfg_template.entry_fallback_max,
            emit_entry_per_method=cfg_template.emit_entry_per_method,
            emit_entry_max=cfg_template.emit_entry_max,
            emit_entry_filter=cfg_template.emit_entry_filter,
            entries_file=cfg_template.entries_file,
            write_scan_summary=cfg_template.write_scan_summary,
        )
        now = time.time()
        cfg_dump = json.dumps(scan_config_dump(cfg), sort_keys=True)
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (job_id, status, progress, current, workspace, zip_path, error, created_at, updated_at, config_json)
                VALUES (?, ?, 0, '', ?, NULL, NULL, ?, ?, ?)
                """,
                (jid, "PENDING", str(ws), now, now, cfg_dump),
            )
            self._conn.commit()
        return self.get(jid)  # type: ignore[return-value]

    def get(self, job_id: str) -> CodeflowJobRecord | None:
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return CodeflowJobRecord(
            job_id=row["job_id"],
            status=row["status"],
            progress=row["progress"],
            current=row["current"],
            workspace=row["workspace"],
            zip_path=row["zip_path"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
        self._set_status(job_id, "RUNNING")

    def mark_completed(self, job_id: str, zip_path: Path | None) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, progress = 100, zip_path = ?, updated_at = ?, current = ? WHERE job_id = ?",
                ("COMPLETED", str(zip_path) if zip_path else None, now, "completed", job_id),
            )
            self._conn.commit()

    def mark_failed(self, job_id: str, err: str) -> None:
        assert self._conn is not None
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?, current = ? WHERE job_id = ?",
                ("FAILED", err[:8000], now, "failed", job_id),
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

    def load_config(self, job_id: str) -> ScanConfig | None:
        assert self._conn is not None
        with self._lock:
            row = self._conn.execute(
                "SELECT config_json FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return scan_config_load(json.loads(row["config_json"]))

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
                ws_path = Path(rec.workspace)

                def on_prog(p: int, cur: str) -> None:
                    self.update_progress(job_id, p, cur)

                lw = LoadedWorkspace(root=cfg.project_root, cleanup_dir=None)

                self.update_progress(job_id, 10, "scan")
                run_scan(cfg, workspace=lw)
                on_prog(90, "zip")

                zpath = ws_path / "output.zip"
                self._zip_output(ws_path, cfg.output_path, zpath)
                self.mark_completed(job_id, zpath)
            except Exception as e:
                self.mark_failed(job_id, str(e))

        threading.Thread(target=target, daemon=True).start()

    def _zip_output(self, workspace: Path, out_dir: Path, dest_zip: Path) -> None:
        dest_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            if out_dir.exists():
                for p in sorted(out_dir.rglob("*")):
                    if p.is_file():
                        zf.write(p, p.relative_to(workspace).as_posix())


def _default_sqlite_path() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / "mdengine-codeflow-jobs" / "jobs.sqlite"
