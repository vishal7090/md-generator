from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Job:
    job_id: str
    workspace: Path
    status: str = "queued"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    zip_path: Path | None = None


class JobStore:
    def __init__(self, base_temp: Path | None, ttl_seconds: int) -> None:
        self._base = base_temp
        self._ttl = ttl_seconds
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._sweeper_started = False

    def _root(self) -> Path:
        import tempfile

        if self._base:
            p = Path(self._base)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return Path(tempfile.gettempdir()) / "playwright-to-md-jobs"

    def start_sweeper(self) -> None:
        if self._sweeper_started:
            return
        self._sweeper_started = True

        def loop() -> None:
            while True:
                time.sleep(60)
                self.sweep()

        threading.Thread(target=loop, daemon=True).start()

    def sweep(self) -> None:
        now = time.time()
        with self._lock:
            dead: list[str] = []
            for jid, job in self._jobs.items():
                if job.status in ("done", "failed") and now - job.created_at > self._ttl:
                    dead.append(jid)
            for jid in dead:
                job = self._jobs.pop(jid, None)
                if job and job.workspace.exists():
                    shutil.rmtree(job.workspace, ignore_errors=True)

    def create_job(self) -> Job:
        jid = str(uuid.uuid4())
        ws = self._root() / jid
        ws.mkdir(parents=True, exist_ok=True)
        job = Job(job_id=jid, workspace=ws)
        with self._lock:
            self._jobs[jid] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def run_async(self, job: Job, fn: Callable[[], None]) -> None:
        def target() -> None:
            try:
                job.status = "running"
                fn()
                job.status = "done"
            except Exception as e:
                job.status = "failed"
                job.error = str(e)

        threading.Thread(target=target, daemon=True).start()

    def remove_after_download(self, job: Job) -> None:
        with self._lock:
            self._jobs.pop(job.job_id, None)
        if job.workspace.exists():
            shutil.rmtree(job.workspace, ignore_errors=True)
