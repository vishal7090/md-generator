from __future__ import annotations

from pathlib import Path

from md_generator.core.schema.adapters.otel import otel_span_to_event
from md_generator.otel.otel_parser import load_otlp_json
from md_generator.otel.otel_spans import parse_otlp_spans


def test_load_otlp_json_spans() -> None:
    path = Path(__file__).resolve().parent / "fixtures" / "otel" / "otlp-traces.json"
    doc = load_otlp_json(path)
    spans = parse_otlp_spans(doc)
    assert len(spans) >= 2
    assert spans[0].trace_id
    ev = otel_span_to_event(spans[0])
    assert ev.signal_type == "trace"
    assert ev.attributes.get("trace_id")


def test_md_otel_cli(tmp_path: Path) -> None:
    from md_generator.otel.cli.main import main

    inp = Path(__file__).resolve().parent / "fixtures" / "otel" / "otlp-traces.json"
    out = tmp_path / "otel-out"
    rc = main(["--input", str(inp), "--output", str(out)])
    assert rc == 0
    assert (out / "trace.md").is_file()
    text = (out / "trace.md").read_text(encoding="utf-8")
    assert "checkout-api" in text or "Spans:" in text
