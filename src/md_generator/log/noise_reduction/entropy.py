from __future__ import annotations

import math
from collections import Counter


def repetition_score(message: str) -> float:
    """Lower score = more repetitive (likely noise)."""
    if not message:
        return 0.0
    counts = Counter(message)
    n = len(message)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_ent = math.log2(min(n, 256)) or 1.0
    return entropy / max_ent
