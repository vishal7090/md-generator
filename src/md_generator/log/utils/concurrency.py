from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def map_threaded(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int,
) -> list[R]:
    if not items:
        return []
    workers = max(1, min(max_workers, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


__all__ = ["map_threaded", "ProcessPoolExecutor"]
