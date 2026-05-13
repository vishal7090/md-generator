from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MDPlugin(Protocol):
    def initialize(self, config: dict[str, Any]) -> None: ...
    def process(self, item: Any) -> Any: ...
    def finalize(self) -> None: ...
