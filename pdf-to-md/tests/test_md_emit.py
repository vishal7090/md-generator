from src.md_emit import escape_cell, table_to_markdown


def test_escape_cell_pipe():
    assert escape_cell("a|b") == "a\\|b"


def test_table_to_markdown():
    md = table_to_markdown([["A", "B"], ["1", "2"]])
    assert "| A | B |" in md
    assert "| --- | --- |" in md
    assert "| 1 | 2 |" in md
