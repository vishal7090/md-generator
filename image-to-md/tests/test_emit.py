from __future__ import annotations

from md_generator.image.emit import markdown_best, markdown_compare, normalize_whitespace, pick_best_text


def test_normalize_whitespace_collapses_long_blank_runs() -> None:
    s = "a  \n\n\n\nb"
    out = normalize_whitespace(s)
    assert out == "a\n\nb"


def test_pick_best_prefers_longer_text_tie_earlier_priority() -> None:
    by = {"A": "hi", "B": "hello"}
    assert pick_best_text(by, ["A", "B"]) == "hello"
    by2 = {"A": "same", "B": "same"}
    assert pick_best_text(by2, ["A", "B"]) == "same"


def test_markdown_compare_structure() -> None:
    md = markdown_compare("Title", [("x.png", {"Tesseract": "one", "EasyOCR": ""})])
    assert md.startswith("# Title")
    assert "## x.png" in md
    assert "### Tesseract" in md
    assert "one" in md


def test_markdown_best_structure() -> None:
    md = markdown_best("T", [("a.jpg", "body")])
    assert "# T" in md
    assert "## a.jpg" in md
    assert "body" in md
