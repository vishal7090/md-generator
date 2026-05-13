from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ClassifierPlugin(Protocol):
    def classify(self, items: list[Any]) -> list[Any]: ...
