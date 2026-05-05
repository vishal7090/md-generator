from __future__ import annotations

from md_generator.codeflow.core.run_config import ScanConfig

__all__ = ["ScanConfig", "run_scan"]


def __getattr__(name: str):
    if name == "run_scan":
        from md_generator.codeflow.core.extractor import run_scan as rs

        return rs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
