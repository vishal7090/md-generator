from __future__ import annotations

from typing import Any

from md_generator.otel.otel_models import OtelSpan


def parse_otlp_spans(doc: dict[str, Any]) -> list[OtelSpan]:
    out: list[OtelSpan] = []
    for rsrc in doc.get("resourceSpans", []) or []:
        service = None
        attrs = (rsrc.get("resource") or {}).get("attributes") or []
        for a in attrs:
            if a.get("key") == "service.name":
                service = (a.get("value") or {}).get("stringValue")
        for scope in rsrc.get("scopeSpans", []) or []:
            for sp in scope.get("spans", []) or []:
                out.append(
                    OtelSpan(
                        trace_id=str(sp.get("traceId", "")),
                        span_id=str(sp.get("spanId", "")),
                        name=str(sp.get("name", "")),
                        service=service,
                    ),
                )
    return out
