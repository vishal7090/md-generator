from __future__ import annotations

from typing import Any

from md_generator.otel.otel_models import OtelLogRecord


def parse_otlp_logs(doc: dict[str, Any]) -> list[OtelLogRecord]:
    out: list[OtelLogRecord] = []
    for rsrc in doc.get("resourceLogs", []) or []:
        for scope in rsrc.get("scopeLogs", []) or []:
            for rec in scope.get("logRecords", []) or []:
                body = rec.get("body", {})
                text = body.get("stringValue") if isinstance(body, dict) else str(body)
                out.append(
                    OtelLogRecord(
                        body=str(text or ""),
                        severity=str(rec.get("severityText") or ""),
                        attributes={},
                    ),
                )
    return out
