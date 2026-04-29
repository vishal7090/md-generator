from __future__ import annotations

from pathlib import Path

from md_generator.codeflow.detectors.liferay_portlet_detector import detect_liferay_portlet_entries
from md_generator.codeflow.models.ir import EntryKind


def test_detect_liferay_portlet_fixture() -> None:
    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "java_portlet"
    path = root / "SamplePortlet.java"
    entries = detect_liferay_portlet_entries(path, root)
    kinds = {e.kind for e in entries}
    assert EntryKind.PORTLET in kinds
    assert any("ProcessAction" in e.label or "lifecycle" in e.label for e in entries)
