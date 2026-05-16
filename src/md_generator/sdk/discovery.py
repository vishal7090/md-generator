from __future__ import annotations

import importlib
from typing import Any


def load_plugins(specs: list[str], protocol: type) -> list[Any]:
    out: list[Any] = []
    for spec in specs:
        if ":" not in spec:
            continue
        mod_name, _, attr = spec.partition(":")
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr, None)
        if obj is None:
            continue
        inst = obj() if callable(obj) else obj
        if isinstance(inst, protocol):
            out.append(inst)
    return out
