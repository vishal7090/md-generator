from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_otlp_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_otlp_bytes(data: bytes, *, protobuf: bool) -> dict[str, Any]:
    if not protobuf:
        return json.loads(data.decode("utf-8"))
    try:
        from google.protobuf.json_format import MessageToDict
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    except ImportError as e:
        raise ImportError("Install mdengine[log-otel-proto] for OTLP protobuf") from e
    req = ExportTraceServiceRequest()
    req.ParseFromString(data)
    return MessageToDict(req)
