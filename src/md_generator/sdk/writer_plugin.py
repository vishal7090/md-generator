from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WriterPlugin(Protocol):
    def write(self, root: object, context: dict[str, Any]) -> None: ...
