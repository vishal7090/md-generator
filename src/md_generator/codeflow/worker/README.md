# Codeflow background workers (optional)

The default [`job_manager`](../api/job_manager.py) runs scans in a **thread** with SQLite job state. For larger deployments you can use **Celery** with a Redis broker.

## Install

```bash
pip install "mdengine[codeflow-worker]"
```

## Environment

- `CELERY_BROKER_URL` — e.g. `redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND` — optional; can match broker URL

## Integration

Import `build_celery_app` from [`celery_optional.py`](celery_optional.py) only after configuring the environment. Wire tasks to the same `run_scan` / zip pipeline your API uses; keep the SQLite job manager as a fallback for single-node setups.

This repository does not start Celery workers by default—deploy them beside your FastAPI instance when you need horizontal scaling.
