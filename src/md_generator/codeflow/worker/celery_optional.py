"""Opt-in Celery app factory. Requires ``mdengine[codeflow-worker]`` and broker env vars."""

from __future__ import annotations

import os
from typing import Any


def build_celery_app(name: str = "mdengine_codeflow") -> Any:
    """Return a Celery app if ``celery`` is installed and ``CELERY_BROKER_URL`` is set.

    Raises ``RuntimeError`` if the broker is unset or Celery is missing.
    """
    broker = os.environ.get("CELERY_BROKER_URL", "").strip()
    if not broker:
        raise RuntimeError("CELERY_BROKER_URL is not set; use the default threaded job manager instead")
    try:
        from celery import Celery
    except ImportError as e:
        raise RuntimeError("Install codeflow-worker extras: pip install mdengine[codeflow-worker]") from e
    backend = os.environ.get("CELERY_RESULT_BACKEND", broker)
    return Celery(name, broker=broker, backend=backend)
