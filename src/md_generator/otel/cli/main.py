from __future__ import annotations

import argparse
import sys
from pathlib import Path

from md_generator.otel.otel_parser import load_otlp_bytes, load_otlp_json
from md_generator.otel.otel_spans import parse_otlp_spans
from md_generator.log.utils.io import ensure_dir, write_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export OpenTelemetry JSON/protobuf to Markdown.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("./otel-docs"))
    p.add_argument("--protobuf", action="store_true")
    ns = p.parse_args(argv)
    if ns.protobuf:
        doc = load_otlp_bytes(ns.input.read_bytes(), protobuf=True)
    else:
        doc = load_otlp_json(ns.input)
    spans = parse_otlp_spans(doc)
    out = ns.output.expanduser().resolve()
    ensure_dir(out)
    lines = ["# OpenTelemetry trace export", "", f"Spans: {len(spans)}", ""]
    for sp in spans[:500]:
        lines.append(f"- `{sp.trace_id}` / `{sp.span_id}` — {sp.name} ({sp.service or 'n/a'})")
    write_text(out / "trace.md", "\n".join(lines) + "\n")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
