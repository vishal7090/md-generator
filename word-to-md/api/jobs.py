from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.settings import WordToMdSettings


@dataclass
class JobRecord:
    job_id: str
    workdir: Path
    status: str  # pending | running | done | error
    error: str | None = None
    created_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self, settings: WordToMdSettings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}

    def _prune_unlocked(self) -> None:
        now = time.time()
        ttl = self._settings.job_ttl_seconds
        dead: list[str] = []
        for jid, rec in self._jobs.items():
            if now - rec.created_at > ttl:
                dead.append(jid)
        for jid in dead:
            rec = self._jobs.pop(jid, None)
            if rec and rec.workdir.exists():
                import shutil

                shutil.rmtree(rec.workdir, ignore_errors=True)

    def create_job(self, workdir: Path) -> JobRecord:
        with self._lock:
            self._prune_unlocked()
            job_id = uuid.uuid4().hex
            rec = JobRecord(job_id=job_id, workdir=workdir, status="pending")
            self._jobs[job_id] = rec
            return rec

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            self._prune_unlocked()
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if not rec:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)

    def delete_workdir(self, job_id: str) -> None:
        with self._lock:
            rec = self._jobs.pop(job_id, None)
        if rec and rec.workdir.exists():
            import shutil

            shutil.rmtree(rec.workdir, ignore_errors=True)


def run_job_in_thread(
    job_id: str,
    store: JobStore,
    fn: Callable[[], None],
) -> None:
    def _run() -> None:
        store.update(job_id, status="running")
        try:
            fn()
        except Exception as e:
            store.update(job_id, status="error", error=str(e))
            return
        store.update(job_id, status="done", error=None)

    threading.Thread(target=_run, daemon=True).start()
