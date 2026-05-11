from __future__ import annotations

from collections.abc import Callable
from typing import Any


def noop_hook(*_args: Any, **_kwargs: Any) -> None:
    return None


LifecycleHooks = tuple[
    Callable[..., None] | None,  # on_start
    Callable[..., None] | None,  # on_stage
    Callable[..., None] | None,  # on_finish
]
