from __future__ import annotations

from md_generator.log.incidents.models import Incident


def dependency_failure_hint(inc: Incident) -> str | None:
    text = " ".join(inc.representative_messages).lower()
    if "redis" in text and "timeout" in text:
        return "redis connectivity or saturation"
    if "postgres" in text or "database" in text:
        return "database dependency degradation"
    return None
