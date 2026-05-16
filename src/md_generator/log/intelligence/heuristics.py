from __future__ import annotations

from md_generator.log.incidents.models import Incident


def score_timeout_pool(inc: Incident) -> float:
    text = " ".join(inc.representative_messages).lower()
    score = 0.0
    if "timeout" in text:
        score += 40.0
    if "pool" in text or "connection" in text:
        score += 30.0
    if len(inc.occurrences) >= 3:
        score += 10.0
    return score
